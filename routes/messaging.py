from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Message, Notification

messaging_bp = Blueprint('messaging', __name__)

@messaging_bp.route('/')
@login_required
def inbox():
    """Show all messages received by the current user."""
    messages = (
        Message.query
        .filter_by(recipient_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )

    unread_count = sum(1 for m in messages if not m.is_read)

    total_messages = len(messages)

    return render_template(
        'inbox/messages.html',
        messages=messages,
        unread_count=unread_count,
        total_messages=total_messages
    )


@messaging_bp.route('/view/<int:message_id>')
@login_required
def view_message(message_id):
    """View a specific message."""
    message = Message.query.get_or_404(message_id)

    # Only allow sender or recipient to view
    if message.recipient_id != current_user.id and message.sender_id != current_user.id:
        flash("You do not have permission to view this message.", "danger")
        return redirect(url_for('messaging.inbox'))

    # Mark message as read if recipient opens it
    # ✅ Mark message as read safely
    if message.recipient_id == current_user.id and not message.is_read:
        message.mark_as_read()
        db.session.commit()

    return render_template('inbox/view_message.html', message=message)


@messaging_bp.route('/start/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def start_conversation(recipient_id):
    """Start or send a message to another user."""
    recipient = User.query.get_or_404(recipient_id)

    if request.method == 'POST':
        subject = request.form.get('subject')
        body = request.form.get('body')

        if not subject or not body:
            flash("Please provide both a subject and message body.", "warning")
            return redirect(request.url)

        # Create new message
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient.id,
            subject=subject.strip(),
            body=body.strip()
        )
        db.session.add(message)
        db.session.commit()  # commit first to get message.id

        # ✅ Create a notification for the recipient (use action_url)
        Notification.create_notification(
            user_id=recipient.id,
            category="message",
            title="New Message Received",
            message=f"You have a new message from {current_user.full_name or current_user.username}.",
            notification_type="system",
            priority="normal",
            related_object_type="message",
            related_object_id=message.id,
            action_url=url_for('messaging.view_message', message_id=message.id),
            action_text="View Message"
        )

        flash("Message sent successfully!", "success")
        return redirect(url_for('messaging.view_message', message_id=message.id))

    return render_template('inbox/new_message.html', recipient=recipient)


@messaging_bp.route('/sent')
@login_required
def sent_messages():
    messages = (
        Message.query
        .filter_by(sender_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )

    return render_template(
        'inbox/sent_messages.html',
        messages=messages
    )


@messaging_bp.route('/mark-read/<int:message_id>', methods=['POST'])
@login_required
def mark_message_read(message_id):
    message = Message.query.get_or_404(message_id)

    if message.recipient_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for('messaging.inbox'))

    message.mark_as_read()
    db.session.commit()

    return redirect(url_for('messaging.view_message', message_id=message.id))


@messaging_bp.route('/reply/<int:message_id>', methods=['GET', 'POST'])
@login_required
def reply_message(message_id):
    """Reply to an existing message."""
    original = Message.query.get_or_404(message_id)

    # Determine who to reply to
    recipient = original.sender if original.recipient_id == current_user.id else original.recipient

    if request.method == 'POST':
        body = request.form.get('body')

        if not body:
            flash("Message body cannot be empty.", "warning")
            return redirect(request.url)

        reply = Message(
            sender_id=current_user.id,
            recipient_id=recipient.id,
            subject=f"Re: {original.subject}",
            body=body.strip()
        )
        db.session.add(reply)
        db.session.commit()  # ✅ must commit before creating notification

        # ✅ Notify the recipient about the reply
        Notification.create_notification(
            user_id=recipient.id,
            category="message",
            title="New Message Reply",
            message=f"{current_user.full_name or current_user.username} replied to your message.",
            notification_type="system",
            priority="normal",
            related_object_type="message",
            related_object_id=reply.id,
            action_url=url_for('messaging.view_message', message_id=reply.id),
            action_text="View Reply"
        )

        flash("Reply sent successfully!", "success")
        return redirect(url_for('messaging.view_message', message_id=reply.id))

    return render_template('inbox/reply_message.html', original=original, recipient=recipient)
