



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



def new_application_notification_template(candidate_name: str, job_title: str, applied_at: str) -> str:
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
        <h2 style="color: #111827; font-size: 18px; margin-bottom: 12px;">
            New Application Received
        </h2>
        <p style="color: #374151; font-size: 14px; margin-bottom: 8px;">
            <strong>{candidate_name}</strong> has applied for the position:
        </p>
        <div style="
            padding: 12px;
            background-color: #f9fafb;
            border-left: 4px solid #6366f1;
            border-radius: 4px;
            margin-bottom: 16px;
        ">
            <p style="color: #111827; font-size: 16px; font-weight: bold; margin: 0;">{job_title}</p>
            <p style="color: #6b7280; font-size: 12px; margin: 4px 0 0 0;">Applied: {applied_at}</p>
        </div>
        <p style="color: #9ca3af; font-size: 12px;">ResumeEZ</p>
    </div>
    """


def application_status_update_template(candidate_name: str, job_title: str, new_status: str) -> str:
    status_colors = {
        "ACCEPTED": "#10b981",
        "REJECTED": "#ef4444",
        "REVIEWING": "#f59e0b",
        "PENDING": "#6b7280",
    }
    color = status_colors.get(new_status.upper(), "#6b7280")
    status_messages = {
        "ACCEPTED": "Congratulations! Your application has been accepted.",
        "REJECTED": "Thank you for your interest. Unfortunately, your application was not selected.",
        "REVIEWING": "Good news! Your application is currently under review.",
        "PENDING": "Your application status has been updated.",
    }
    message = status_messages.get(new_status.upper(), "Your application status has been updated.")

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
        <h2 style="color: #111827; font-size: 18px; margin-bottom: 12px;">
            Application Status Update
        </h2>
        <p style="color: #374151; font-size: 14px; margin-bottom: 8px;">
            Hi <strong>{candidate_name}</strong>,
        </p>
        <p style="color: #374151; font-size: 14px; margin-bottom: 16px;">
            {message}
        </p>
        <div style="
            padding: 12px;
            background-color: #f9fafb;
            border-left: 4px solid {color};
            border-radius: 4px;
            margin-bottom: 16px;
        ">
            <p style="color: #111827; font-size: 14px; margin: 0;">
                Position: <strong>{job_title}</strong>
            </p>
            <p style="color: {color}; font-size: 14px; font-weight: bold; margin: 4px 0 0 0;">
                Status: {new_status.title()}
            </p>
        </div>
        <p style="color: #9ca3af; font-size: 12px;">ResumeEZ Team</p>
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
