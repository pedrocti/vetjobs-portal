# utils/settings_utils.py

from models import PaymentSetting

def get_setting(key, default=None):
    setting = PaymentSetting.query.filter_by(setting_key=key).first()
    return float(setting.value) if setting else default


def get_pricing():
    return {
        "starter": get_setting("starter_plan_amount", 0),
        "professional": get_setting("professional_plan_amount", 59000),
        "enterprise": get_setting("enterprise_plan_amount", 129000),
        "verification_fee": get_setting("verification_fee", 2000),
        "boost_fee": get_setting("boost_fee", 1000),
    }