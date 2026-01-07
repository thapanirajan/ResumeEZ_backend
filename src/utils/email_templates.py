



def verification_email_template(token: str) -> str:
    return f"""
    <div style="
        max-width: 480px;
        margin: 0 auto;
        padding: 24px;
        font-family: Arial, Helvetica, sans-serif;
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
    ">
        <h2 style="
            color: #111827;
            font-size: 18px;
            margin-bottom: 12px;
        ">
            Verify your email
        </h2>

        <p style="
            color: #374151;
            font-size: 14px;
            margin-bottom: 20px;
        ">
            Use the verification code below to confirm your email address.
        </p>

        <div style="
            padding: 12px;
            text-align: center;
            font-size: 22px;
            font-weight: bold;
            letter-spacing: 4px;
            color: #111827;
            background-color: #f9fafb;
            border: 1px dashed #d1d5db;
            border-radius: 4px;
            margin-bottom: 20px;
        ">
            {token}
        </div>

        <p style="
            color: #6b7280;
            font-size: 12px;
            margin-bottom: 16px;
        ">
            This code will expire in 5 minutes.
        </p>

        <p style="
            color: #9ca3af;
            font-size: 12px;
        ">
            ResumeEZ
        </p>
    </div>
    """



def password_reset_email_template(token: str) -> str:
    return f"""
    <div style="
        max-width: 480px;
        margin: 0 auto;
        padding: 24px;
        font-family: Arial, Helvetica, sans-serif;
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
    ">
        <h2 style="
            color: #111827;
            font-size: 18px;
            margin-bottom: 12px;
        ">
            Reset your password
        </h2>

        <p style="
            color: #374151;
            font-size: 14px;
            margin-bottom: 20px;
        ">
            Use the code below to reset your password.
        </p>

        <div style="
            padding: 12px;
            text-align: center;
            font-size: 22px;
            font-weight: bold;
            letter-spacing: 4px;
            color: #111827;
            background-color: #f9fafb;
            border: 1px dashed #d1d5db;
            border-radius: 4px;
            margin-bottom: 20px;
        ">
            {token}
        </div>

        <p style="
            color: #6b7280;
            font-size: 12px;
            margin-bottom: 16px;
        ">
            This code will expire in 10 minutes.
        </p>

        <p style="
            color: #9ca3af;
            font-size: 12px;
        ">
            ResumeEZ Team
        </p>
    </div>
    """
