from django.conf import settings

from .ami_client import SocketAmiClient
from .schedule_publisher import AmiSchedulePublisher, NoOpSchedulePublisher


def build_schedule_publisher():
    if not settings.ASTERISK_AMI_ENABLED:
        return NoOpSchedulePublisher()

    ami_client = SocketAmiClient(
        host=settings.ASTERISK_AMI_HOST,
        port=settings.ASTERISK_AMI_PORT,
        username=settings.ASTERISK_AMI_USERNAME,
        password=settings.ASTERISK_AMI_PASSWORD,
        timeout=settings.ASTERISK_AMI_TIMEOUT,
    )

    return AmiSchedulePublisher(ami_client)
