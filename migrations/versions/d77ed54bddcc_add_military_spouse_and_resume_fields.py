"""Add military spouse and resume fields

Revision ID: d77ed54bddcc
Revises: 7552e0c46f94
Create Date: 2026-03-04 02:48:53.706958
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd77ed54bddcc'
down_revision = '7552e0c46f94'
branch_labels = None
depends_on = None


def upgrade():
    # ### Remove unsafe drop commands ###
    # op.drop_table('training_partners')
    # op.drop_table('veteran_profile')
    # op.drop_table('training_program_submissions')

    # Update training_programs table (dropping old AI / partner fields)
    with op.batch_alter_table('training_programs', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('training_programs_partner_id_fkey'), type_='foreignkey')
        batch_op.drop_column('ai_flyer_image')
        batch_op.drop_column('ai_landing_html')
        batch_op.drop_column('partner_id')
        batch_op.drop_column('ai_flyer_html')
        batch_op.drop_column('qr_path')

    # Update users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('onboarding_completed',
                              existing_type=sa.BOOLEAN(),
                              nullable=True,
                              existing_server_default=sa.text('false'))


def downgrade():
    # Revert users table changes
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('onboarding_completed',
                              existing_type=sa.BOOLEAN(),
                              nullable=False,
                              existing_server_default=sa.text('false'))

    # Revert training_programs table changes
    with op.batch_alter_table('training_programs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('qr_path', sa.VARCHAR(length=255), nullable=True))
        batch_op.add_column(sa.Column('ai_flyer_html', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('partner_id', sa.INTEGER(), nullable=False))
        batch_op.add_column(sa.Column('ai_landing_html', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('ai_flyer_image', sa.VARCHAR(length=500), nullable=True))
        batch_op.create_foreign_key(batch_op.f('training_programs_partner_id_fkey'),
                                    'training_partners', ['partner_id'], ['id'])