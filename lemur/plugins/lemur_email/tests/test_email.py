import os
from datetime import timedelta

import arrow
from moto import mock_ses

from lemur.certificates.schemas import certificate_notification_output_schema
from lemur.plugins.lemur_email.plugin import render_html
from lemur.tests.factories import CertificateFactory
from lemur.tests.test_messaging import verify_sender_email

dir_path = os.path.dirname(os.path.realpath(__file__))


def get_options():
    return [
        {"name": "interval", "value": 10},
        {"name": "unit", "value": "days"},
        {"name": "recipients", "value": "person1@example.com,person2@example.com"},
    ]


def test_render_expiration(certificate, endpoint):

    new_cert = CertificateFactory()
    new_cert.replaces.append(certificate)

    assert render_html("expiration", get_options(), [certificate_notification_output_schema.dump(certificate).data])


def test_render_rotation(certificate, endpoint):
    certificate.endpoints.append(endpoint)

    assert render_html("rotation", get_options(), certificate_notification_output_schema.dump(certificate).data)


def test_render_rotation_failure(pending_certificate):
    assert render_html("failed", get_options(), certificate_notification_output_schema.dump(pending_certificate).data)


@mock_ses
def test_send_expiration_notification():
    from lemur.notifications.messaging import send_expiration_notifications
    from lemur.tests.factories import CertificateFactory
    from lemur.tests.factories import NotificationFactory

    now = arrow.utcnow()
    in_ten_days = now + timedelta(days=10, hours=1)  # a bit more than 10 days since we'll check in the future
    certificate = CertificateFactory()
    notification = NotificationFactory(plugin_name="email-notification")

    certificate.not_after = in_ten_days
    certificate.notifications.append(notification)
    certificate.notifications[0].options = get_options()

    verify_sender_email()
    assert send_expiration_notifications([]) == (3, 0)  # owner, recipients (only counted as 1), and security


@mock_ses
def test_send_rotation_notification(endpoint, source_plugin):
    from lemur.notifications.messaging import send_rotation_notification
    from lemur.deployment.service import rotate_certificate

    new_certificate = CertificateFactory()
    rotate_certificate(endpoint, new_certificate)
    assert endpoint.certificate == new_certificate

    verify_sender_email()
    assert send_rotation_notification(new_certificate)


@mock_ses
def test_send_pending_failure_notification(user, pending_certificate, async_issuer_plugin):
    from lemur.notifications.messaging import send_pending_failure_notification

    verify_sender_email()
    assert send_pending_failure_notification(pending_certificate)


def test_filter_recipients(certificate, endpoint):
    from lemur.plugins.lemur_email.plugin import EmailNotificationPlugin

    options = [{"name": "recipients", "value": "security@example.com,bob@example.com,joe@example.com"}]
    assert EmailNotificationPlugin.filter_recipients(options, []) == ["security@example.com", "bob@example.com",
                                                                      "joe@example.com"]
    assert EmailNotificationPlugin.filter_recipients(options, ["security@example.com"]) == ["bob@example.com",
                                                                                            "joe@example.com"]
    assert EmailNotificationPlugin.filter_recipients(options, ["security@example.com", "bob@example.com",
                                                               "joe@example.com"]) == []
