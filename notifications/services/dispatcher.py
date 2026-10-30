from notifications.services.channel_factory import ChannelFactory

class NotificationDispatcher:

    def dispatch(self, notification):
        channel = ChannelFactory.create_channel(notification.channel)
        return channel.send_notification(notification)