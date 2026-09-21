import uuid
import time
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

ONLINE_TIMEOUT = 15  # seconds
MESSAGE_TIMEOUT = 300  # 5 minutes

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_sync(request):
    """
    Mark current user as online, return list of online users, 
    and return messages for the current user.
    """
    user = request.user
    now = time.time()
    
    # --- 1. Online Presence ---
    online_users = cache.get('chat_online_users', {})
    online_users[user.id] = {
        'id': user.id,
        'name': user.display_name,
        'role': user.role,
        'avatar_color': user.avatar_color,
        'avatar_icon': user.avatar_icon,
        'last_seen': now
    }
    
    active_users = []
    cleaned_online_users = {}
    for uid, data in online_users.items():
        if now - data['last_seen'] < ONLINE_TIMEOUT:
            cleaned_online_users[uid] = data
            if uid != user.id:
                active_users.append({
                    'id': data['id'],
                    'name': data['name'],
                    'role': data['role'],
                    # .get(): people already in the cache from before this feature have no avatar yet.
                    'avatar_color': data.get('avatar_color', ''),
                    'avatar_icon': data.get('avatar_icon', ''),
                })
                
    cache.set('chat_online_users', cleaned_online_users, timeout=ONLINE_TIMEOUT * 2)
    
    # --- 2. Fetch Messages ---
    inbox = cache.get(f'chat_inbox_{user.id}', [])
    outbox = cache.get(f'chat_outbox_{user.id}', [])
    
    all_msgs = inbox + outbox
    all_msgs.sort(key=lambda x: x['timestamp'])
    
    return Response({
        'online_users': active_users,
        'messages': all_msgs
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_messages(request):
    """
    POST: Send a message to a specific user.
    """
    user = request.user
    
    try:
        to_id = request.data.get('to_id')
        text = request.data.get('text', '').strip()
        
        if not to_id or not text:
            return Response({'error': 'to_id and text are required'}, status=400)
            
        msg = {
            'id': str(uuid.uuid4()),
            'from_id': user.id,
            'from_name': user.display_name,
            'to_id': int(to_id),
            'text': text,
            'timestamp': time.time() * 1000  # JS milliseconds
        }
        
        # Save to recipient's inbox
        inbox_key = f'chat_inbox_{to_id}'
        inbox = cache.get(inbox_key, [])
        if not isinstance(inbox, list):
            inbox = []
        inbox.append(msg)
        cache.set(inbox_key, inbox[-50:], timeout=MESSAGE_TIMEOUT)
        
        # Save to sender's outbox
        outbox_key = f'chat_outbox_{user.id}'
        outbox = cache.get(outbox_key, [])
        if not isinstance(outbox, list):
            outbox = []
        outbox.append(msg)
        cache.set(outbox_key, outbox[-50:], timeout=MESSAGE_TIMEOUT)
        
        return Response({'success': True, 'message': msg})
    except Exception as e:
        import traceback
        return Response({'error': str(e), 'traceback': traceback.format_exc()}, status=500)
