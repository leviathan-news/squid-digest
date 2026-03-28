"""HTML email templates for Squid Digest optimized for Ghost email delivery."""

from typing import List


def admin_notification_template(digest_path: str, github_url: str, is_edit: bool = False) -> str:
    """Generate HTML template for admin notification email optimized for Ghost."""
    action = "edited" if is_edit else "ready for review"
    subject_prefix = "✏️" if is_edit else "🔍"
    title = f"{subject_prefix} Daily Digest Draft {action.title()}"
    
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; width: 100%; max-width: 100%; margin: 0; padding: 0;">
        <table role="presentation" style="width: 100%; border-collapse: collapse; margin: 0; padding: 0;">
            <tr>
                <td style="padding: 0;">
                    <div style="max-width: 650px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
                            <h1 style="margin: 0; font-size: 24px;">{title}</h1>
                            <p style="margin: 10px 0 0 0; opacity: 0.9;">Squid Digest - AI-powered crypto trading signals</p>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 30px; border-radius: 8px; margin-bottom: 20px;">
                            <p>Hello Admin,</p>
                            
                            <p>The daily crypto digest has been generated and is {action}.</p>
                            
                            <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 6px; margin: 20px 0;">
                                <strong>⏰ Review Window:</strong> You have 1 hour to review and edit the draft before it's sent to subscribers at 6 AM PT.
                            </div>
                            
                            <p><strong>File:</strong> {digest_path}</p>
                            <p><strong>GitHub Link:</strong> <a href="{github_url}" style="color: #007bff;">{github_url}</a></p>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{github_url}" style="display: inline-block; background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Review Draft on GitHub</a>
                            </div>
                            
                            <p><strong>Instructions:</strong></p>
                            <ul>
                                <li>Click the link above to view the draft</li>
                                <li>Make any necessary edits directly in GitHub</li>
                                <li>If you edit the file, all admins will be notified of the changes</li>
                                <li>The digest will be sent automatically at 6 AM PT regardless of edits</li>
                            </ul>
                        </div>
                        
                        <div style="text-align: center; color: #666; font-size: 14px;">
                            <p>This is an automated message from Squid Digest</p>
                            <p>Generated at {{{{ timestamp }}}}</p>
                        </div>
                    </div>
                </td>
            </tr>
        </table>
    </div>
    """


def public_digest_template(content: str, date: str) -> str:
    """Generate HTML template for public digest email optimized for Ghost."""
    # Generate the post title that matches what's set in Ghost
    post_title = f"🦑 Leviathan News Daily Digest - {date}"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            /* Desktop styles - default */
            .container {{
                padding: 20px !important;
            }}
            .content {{
                padding: 20px !important;
            }}
            .header-padding {{
                padding: 30px !important;
            }}
            .inner-content {{
                padding: 20px !important;
            }}
            /* Mobile styles - minimal padding, simplified layout */
            @media only screen and (max-width: 600px) {{
                .container {{
                    width: 100% !important;
                    max-width: 100% !important;
                    padding: 0 !important;
                }}
                .content {{
                    padding: 2px !important;
                    border-radius: 0 !important;
                }}
                .header-padding {{
                    padding: 15px 5px !important;
                    border-radius: 0 !important;
                    margin-bottom: 10px !important;
                }}
                .inner-content {{
                    padding: 2px !important;
                    border-radius: 0 !important;
                }}
                /* Remove all padding/margins from nested divs on mobile */
                .inner-content > div {{
                    padding: 2px !important;
                    margin: 0 !important;
                }}
                /* SQUID Pass section - full width on mobile with minimal padding */
                .squid-pass-section {{
                    padding: 4px !important;
                    margin: 8px 0 !important;
                    width: 100% !important;
                    max-width: 100% !important;
                }}
                /* Story sections - minimal padding */
                .story-section {{
                    padding: 4px !important;
                    margin: 8px 0 !important;
                }}
                .story-section > div {{
                    padding: 4px !important;
                }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5;">
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; width: 100%; max-width: 100%; margin: 0; padding: 0;">
        <table role="presentation" style="width: 100%; border-collapse: collapse; margin: 0; padding: 0; background-color: #f5f5f5;">
            <tr>
                <td style="padding: 0;">
                    <table role="presentation" class="container" style="max-width: 650px; margin: 0 auto; width: 100%;">
                        <tr>
                            <td style="padding: 0;">
                                <!-- Ghost automatically shows the post title, so we start directly with the content header -->
                                <div class="header-padding" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;">
                                    <h1 style="margin: 0; font-size: 28px;">🦑 Leviathan News Daily Digest</h1>
                                    <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 18px;">{date}</p>
                                    <p style="margin: 10px 0 0 0; opacity: 0.8;">Squid Digest - AI-powered insights for crypto natives</p>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 0;">
                                <div class="content" style="background: white; border-radius: 8px; margin-bottom: 20px;">
                                    <div class="inner-content" style="background: #f8f9fa; border-radius: 6px;">
                                        {content}
                                    </div>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 0;">
                                <div style="text-align: center; color: #666; font-size: 14px;">
                                    <p>Generated by Squid Digest - AI-powered trading signals for crypto natives</p>
                                    <p>Powered by Leviathan News & Perplexity AI</p>
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </div>
    </body>
    </html>
    """


def edit_notification_template(digest_path: str, github_url: str, changes_summary: str = "") -> str:
    """Generate HTML template for edit notification email optimized for Ghost."""
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; width: 100%; max-width: 100%; margin: 0; padding: 0;">
        <table role="presentation" style="width: 100%; border-collapse: collapse; margin: 0; padding: 0;">
            <tr>
                <td style="padding: 0;">
                    <div style="max-width: 650px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
                            <h1 style="margin: 0; font-size: 24px;">✏️ Digest Draft Edited</h1>
                            <p style="margin: 10px 0 0 0; opacity: 0.9;">Review Required - Changes Detected</p>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 30px; border-radius: 8px; margin-bottom: 20px;">
                            <p>Hello Admin,</p>
                            
                            <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 6px; margin: 20px 0;">
                                <strong>⚠️ Changes Detected:</strong> The daily digest draft has been edited and requires your review.
                            </div>
                            
                            <p><strong>File:</strong> {digest_path}</p>
                            <p><strong>GitHub Link:</strong> <a href="{github_url}" style="color: #007bff;">{github_url}</a></p>
                            
                            {f'<p><strong>Changes Summary:</strong> {changes_summary}</p>' if changes_summary else ''}
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{github_url}" style="display: inline-block; background: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Review Changes on GitHub</a>
                            </div>
                            
                            <p><strong>Next Steps:</strong></p>
                            <ul>
                                <li>Review the changes made to the digest</li>
                                <li>Ensure the content meets quality standards</li>
                                <li>The digest will still be sent automatically at 6 AM PT</li>
                            </ul>
                        </div>
                        
                        <div style="text-align: center; color: #666; font-size: 14px;">
                            <p>This is an automated message from Squid Digest</p>
                            <p>Generated at {{{{ timestamp }}}}</p>
                        </div>
                    </div>
                </td>
            </tr>
        </table>
    </div>
    """