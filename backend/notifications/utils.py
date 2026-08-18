from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def broadcast_ws_event(branch_id, event_type, data):
    """
    Hàm đẩy tin nhắn vào Redis để WebSocket Consumer phát sóng.
    - Bắn 1 bản copy cho Chi nhánh.
    - Bắn 1 bản copy cho Admin/Owner.
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    payload = {
        # 'type' BẮT BUỘC phải khớp với tên hàm async trong Consumer (send_notification)
        "type": "send_notification",
        "event_type": event_type,
        "branch_id": str(branch_id) if branch_id else None,
        "data": data
    }

    # 1. Bắn cho kênh của Chi nhánh (Nếu có)
    if branch_id:
        async_to_sync(channel_layer.group_send)(
            f"branch_{branch_id}",
            payload
        )

    # 2. Bắn cho kênh của Owner (Luôn luôn bắn để Admin tổng hợp)
    async_to_sync(channel_layer.group_send)(
        "admin_global",
        payload
    )