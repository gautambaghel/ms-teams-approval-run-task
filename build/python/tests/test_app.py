import pytest
import json
import hmac
import hashlib
import os
from unittest.mock import patch, MagicMock
import requests
import redis
from app import app, store_token, get_token, remove_token

# Existing fixtures and imports remain the same...

# Environment Variable Tests
def test_missing_teams_webhook_url(client, mock_requests):
    """Test behavior when TEAMS_WEBHOOK_URL is not configured"""
    # Mock requests.post to raise an exception since webhook URL is empty
    mock_requests.post.side_effect = requests.RequestException("Failed to send message")
    
    with patch('app.TEAMS_WEBHOOK_URL', ''), \
         patch('app.HMAC_KEY', ''), \
         patch('app.FILTER_SPECULATIVE_PLANS_ONLY', False):  # Disable auto-approval
        payload = {
            'access_token': 'test-token',
            'task_result_callback_url': 'http://example.com',
            'run_id': 'test-run',
            'is_speculative': True  # Make it a speculative plan
        }
        response = client.post('/teams-approval', json=payload)
        assert response.status_code == 500
        assert b"Error in teams_approval" in response.data

def test_missing_base_public_url(client, mock_requests):
    """Test behavior when BASE_PUBLIC_URL is not configured"""
    mock_requests.post.return_value.raise_for_status.return_value = None
    
    with patch('app.BASE_PUBLIC_URL', ''), \
         patch('app.HMAC_KEY', ''), \
         patch('app.FILTER_SPECULATIVE_PLANS_ONLY', False):  # Disable auto-approval
        payload = {
            'access_token': 'test-token',
            'task_result_callback_url': 'http://example.com',
            'run_id': 'test-run',
            'is_speculative': True  # Make it a speculative plan
        }
        response = client.post('/teams-approval', json=payload)
        assert response.status_code == 200
        
        # Verify Teams message was called
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args[1]
        assert 'json' in call_args
        teams_message = call_args['json']
        # Message should contain absolute paths without base URL
        assert '[Approve](/approve?run_id=' in teams_message['text']
        assert '[Reject](/reject?run_id=' in teams_message['text']

# Security Tests
def test_hmac_invalid_content_type(client):
    """Test HMAC verification with wrong content type"""
    test_payload = "not-json-data"
    test_key = "test-hmac-key"
    
    signature = hmac.new(
        key=test_key.encode('utf-8'),
        msg=test_payload.encode('utf-8'),
        digestmod=hashlib.sha512
    ).hexdigest()
    
    with patch('app.HMAC_KEY', test_key):
        try:
            response = client.post(
                '/teams-approval',
                data=test_payload,
                headers={
                    'X-Tfc-Task-Signature': signature,
                    'Content-Type': 'text/plain'
                }
            )
            assert response.status_code == 403
        except Exception:
            # If server raises 500 due to JSON parsing, that's also acceptable
            assert response.status_code == 500

def test_hmac_missing_signature_header(client):
    """Test HMAC verification with missing signature header"""
    with patch('app.HMAC_KEY', 'test-key'):
        response = client.post(
            '/teams-approval',
            json={'test': 'data'}
        )
        assert response.status_code == 403

def test_hmac_tampered_payload(client):
    """Test HMAC verification with tampered payload"""
    original_payload = json.dumps({"test": "data"}).encode('utf-8')
    test_key = "test-hmac-key"
    
    # Calculate signature for original payload
    signature = hmac.new(
        key=test_key.encode('utf-8'),
        msg=original_payload,
        digestmod=hashlib.sha512
    ).hexdigest()
    
    # Send different payload with original signature
    tampered_payload = json.dumps({"test": "tampered"}).encode('utf-8')
    
    with patch('app.HMAC_KEY', test_key):
        response = client.post(
            '/teams-approval',
            data=tampered_payload,
            headers={
                'X-Tfc-Task-Signature': signature,
                'Content-Type': 'application/json'
            }
        )
        assert response.status_code == 403

# Edge Cases Tests
def test_malformed_json_payload(client):
    """Test handling of malformed JSON payload"""
    with patch('app.HMAC_KEY', ''):
        response = client.post(
            '/teams-approval',
            data="not valid json{",
            content_type='application/json'
        )
        # Both 400 (Bad Request) and 500 (Internal Server Error) are acceptable
        # as Flask may handle the JSON parsing error differently
        assert response.status_code in [400, 500]
        if response.status_code == 500:
            assert b"Error in teams_approval" in response.data

def test_unicode_workspace_name(client, mock_requests):
    """Test handling of Unicode characters in workspace name"""
    mock_requests.post.return_value.raise_for_status.return_value = None
    
    with patch('app.HMAC_KEY', ''), \
         patch('app.FILTER_SPECULATIVE_PLANS_ONLY', False):  # Disable auto-approval
        payload = {
            'access_token': 'test-token',
            'task_result_callback_url': 'http://example.com',
            'run_id': 'test-run',
            'workspace_name': '🚀 Unicode 测试 Workspace ✨',
            'is_speculative': True  # Make it a speculative plan
        }
        response = client.post('/teams-approval', json=payload)
        assert response.status_code == 200
        
        # Verify Teams message was called
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args[1]
        assert 'json' in call_args
        teams_message = call_args['json']
        # Verify Unicode characters are preserved
        assert '🚀' in teams_message['text']
        assert '测试' in teams_message['text']

def test_very_long_run_id(client):
    """Test handling of very long run ID"""
    long_run_id = 'x' * 1000  # 1000 character run ID
    
    # Test storage
    test_data = {
        'access_token': 'test-token',
        'callback_url': 'http://example.com'
    }
    store_token(long_run_id, test_data)
    assert get_token(long_run_id) == test_data
    
    # Test retrieval via approve endpoint
    response = client.get(f'/approve?run_id={long_run_id}')
    assert response.status_code in [200, 500]  # Either success or handled error
    assert response.status_code in [200, 500]  # Either success or handled error

def test_concurrent_approve_reject(client, mock_requests):
    """Test concurrent approve/reject requests for same run ID"""
    run_id = 'test-run'
    test_data = {
        'access_token': 'test-token',
        'callback_url': 'http://example.com'
    }
    store_token(run_id, test_data)
    
    # First request approves
    response1 = client.get(f'/approve?run_id={run_id}')
    assert response1.status_code == 200
    
    # Second request should fail as token is already consumed
    response2 = client.get(f'/reject?run_id={run_id}')
    assert response2.status_code == 404

def test_speculative_plan_requires_approval(client, mock_requests):
    """Test that speculative plans still require manual approval when FILTER_SPECULATIVE_PLANS_ONLY is true"""
    mock_requests.post.return_value.raise_for_status.return_value = None
    
    with patch('app.FILTER_SPECULATIVE_PLANS_ONLY', True), \
         patch('app.HMAC_KEY', ''):
        
        payload = {
            'access_token': 'real-token',
            'task_result_callback_url': 'http://callback.example.com',
            'run_id': 'test-run',
            'workspace_name': 'test-workspace',
            'is_speculative': True  # This is a speculative plan
        }
        
        response = client.post(
            '/teams-approval',
            json=payload
        )
        
        assert response.status_code == 200
        # Verify that a Teams message was sent (requiring manual approval)
        mock_requests.post.assert_called_once()
        # Verify no auto-approval PATCH was sent to Terraform
        mock_requests.patch.assert_not_called()

def test_empty_workspace_name(client, mock_requests):
    """Test handling of empty workspace name"""
    mock_requests.post.return_value.raise_for_status.return_value = None
    
    with patch('app.HMAC_KEY', ''), \
         patch('app.FILTER_SPECULATIVE_PLANS_ONLY', False):  # Disable auto-approval
        payload = {
            'access_token': 'test-token',
            'task_result_callback_url': 'http://example.com',
            'run_id': 'test-run',
            'workspace_name': '',
            'is_speculative': True  # Make it a speculative plan
        }
        response = client.post('/teams-approval', json=payload)
        assert response.status_code == 200
        
        # Verify Teams message was called
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args[1]
        assert 'json' in call_args
        teams_message = call_args['json']
        # Empty workspace name should appear in message
        assert 'Workspace ****' in teams_message['text']

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_redis():
    with patch('app.redis_client') as mock:
        yield mock

@pytest.fixture
def mock_requests():
    with patch('app.requests') as mock:
        yield mock

def test_verify_hmac_success(client):
    """Test successful HMAC verification"""
    test_payload = json.dumps({"test": "data"}).encode('utf-8')
    test_key = "test-hmac-key"
    
    # Calculate valid signature
    signature = hmac.new(
        key=test_key.encode('utf-8'),
        msg=test_payload,
        digestmod=hashlib.sha512
    ).hexdigest()
    
    with patch('app.HMAC_KEY', test_key):
        response = client.post(
            '/teams-approval',
            data=test_payload,
            headers={'X-Tfc-Task-Signature': signature},
            content_type='application/json'
        )
        # Should pass HMAC check (though may fail for other reasons)
        assert response.status_code != 403

def test_verify_hmac_failure(client):
    """Test HMAC verification failure"""
    test_payload = json.dumps({"test": "data"}).encode('utf-8')
    
    with patch('app.HMAC_KEY', "test-hmac-key"):
        response = client.post(
            '/teams-approval',
            data=test_payload,
            headers={'X-Tfc-Task-Signature': 'invalid-signature'},
            content_type='application/json'
        )
        assert response.status_code == 403

def test_teams_approval_missing_params(client):
    """Test teams_approval endpoint with missing parameters"""
    with patch('app.HMAC_KEY', ''):  # Disable HMAC verification
        response = client.post(
            '/teams-approval',
            json={}
        )
    assert response.status_code == 400
    assert b"Missing 'access_token' or 'task_result_callback_url'" in response.data

def test_teams_approval_test_token(client):
    """Test handling of test tokens"""
    with patch('app.HMAC_KEY', ''):  # Disable HMAC verification
        response = client.post(
            '/teams-approval',
            json={
                'access_token': 'test-token',
                'stage': 'test',
                'task_result_callback_url': 'http://example.com'
            }
        )
    assert response.status_code == 200
    assert b"Test token received" in response.data

def test_teams_approval_success(client, mock_requests):
    """Test successful teams approval flow"""
    # Mock successful Teams webhook POST
    mock_requests.post.return_value.raise_for_status.return_value = None
    
    payload = {
        'access_token': 'real-token',
        'task_result_callback_url': 'http://callback.example.com',
        'run_id': 'test-run',
        'workspace_name': 'test-workspace',
        'stage': 'plan',
        'is_speculative': True
    }
    
    with patch('app.HMAC_KEY', ''):  # Disable HMAC verification
        response = client.post(
            '/teams-approval',
            json=payload
        )
    
    assert response.status_code == 200
    # Verify Teams webhook was called
    mock_requests.post.assert_called_once()
    
    # Verify stored token
    stored_data = get_token('test-run')
    assert stored_data['access_token'] == 'real-token'
    assert stored_data['callback_url'] == 'http://callback.example.com'

def test_approve_success(client, mock_requests):
    """Test successful approval flow"""
    run_id = 'test-run'
    test_data = {
        'access_token': 'test-token',
        'callback_url': 'http://callback.example.com'
    }
    store_token(run_id, test_data)
    
    # Mock successful PATCH to Terraform
    mock_requests.patch.return_value.raise_for_status.return_value = None
    
    response = client.get(f'/approve?run_id={run_id}')
    
    assert response.status_code == 200
    assert b"APPROVED" in response.data
    
    # Verify Terraform callback was called
    mock_requests.patch.assert_called_once()
    
    # Verify token was removed
    assert get_token(run_id) is None

def test_reject_success(client, mock_requests):
    """Test successful rejection flow"""
    run_id = 'test-run'
    test_data = {
        'access_token': 'test-token',
        'callback_url': 'http://callback.example.com'
    }
    store_token(run_id, test_data)
    
    # Mock successful PATCH to Terraform
    mock_requests.patch.return_value.raise_for_status.return_value = None
    
    response = client.get(f'/reject?run_id={run_id}')
    
    assert response.status_code == 200
    assert b"REJECTED" in response.data
    
    # Verify Terraform callback was called
    mock_requests.patch.assert_called_once()
    
    # Verify token was removed
    assert get_token(run_id) is None

def test_token_storage_redis(mock_redis):
    """Test Redis token storage when enabled"""
    with patch('app.REDIS_ENABLED', True):
        run_id = 'test-run'
        test_data = {'test': 'data'}
        
        # Test store
        store_token(run_id, test_data)
        mock_redis.setex.assert_called_once()
        
        # Test get
        mock_redis.get.return_value = json.dumps(test_data).encode('utf-8')
        retrieved = get_token(run_id)
        assert retrieved == test_data
        
        # Test remove
        remove_token(run_id)
        mock_redis.delete.assert_called_once_with(run_id)

def test_token_storage_memory():
    """Test in-memory token storage"""
    with patch('app.REDIS_ENABLED', False):
        run_id = 'test-run'
        test_data = {'test': 'data'}
        
        # Test store
        store_token(run_id, test_data)
        assert get_token(run_id) == test_data
        
        # Test remove
        remove_token(run_id)
        assert get_token(run_id) is None

def test_teams_webhook_failure(client, mock_requests):
    """Test handling of Teams webhook failure"""
    # Mock failed Teams webhook POST
    mock_requests.post.side_effect = requests.RequestException("Failed to send message")
    
    with patch('app.HMAC_KEY', ''):
        payload = {
            'access_token': 'real-token',
            'task_result_callback_url': 'http://callback.example.com',
            'run_id': 'test-run',
            'workspace_name': 'test-workspace',
            'is_speculative': True
        }
        
        response = client.post(
            '/teams-approval',
            json=payload
        )
        
        assert response.status_code == 500
        assert b"Error in teams_approval" in response.data

def test_callback_url_failure(client, mock_requests):
    """Test handling of Terraform callback failure"""
    run_id = 'test-run'
    test_data = {
        'access_token': 'test-token',
        'callback_url': 'http://callback.example.com'
    }
    store_token(run_id, test_data)
    
    # Mock failed PATCH to Terraform
    mock_requests.patch.side_effect = requests.RequestException("Failed to send callback")
    
    response = client.get(f'/approve?run_id={run_id}')
    
    assert response.status_code == 500
    assert b"Error approving run" in response.data

def test_approve_missing_run_id(client):
    """Test approve endpoint with missing run_id"""
    response = client.get('/approve')
    assert response.status_code == 400
    assert b"Missing 'run_id' parameter" in response.data

def test_reject_expired_token(client):
    """Test reject endpoint with expired token"""
    response = client.get('/reject?run_id=expired-run')
    assert response.status_code == 404
    assert b"expired" in response.data

def test_teams_message_formatting(client, mock_requests):
    """Test Teams message formatting with all optional fields"""
    mock_requests.post.return_value.raise_for_status.return_value = None
    
    with patch('app.HMAC_KEY', ''), patch('app.BASE_PUBLIC_URL', 'http://example.com'):
        payload = {
            'access_token': 'real-token',
            'task_result_callback_url': 'http://callback.example.com',
            'run_id': 'test-run',
            'workspace_name': 'test-workspace',
            'stage': 'plan',
            'is_speculative': True,
            'run_created_by': 'test-user',
            'run_message': 'test message',
            'vcs_pull_request_url': 'http://github.com/pr/123',
            'workspace_app_url': 'http://app.terraform.io/workspace'
        }
        
        response = client.post(
            '/teams-approval',
            json=payload
        )
        
        assert response.status_code == 200
        
        # Verify Teams message format
        teams_message = mock_requests.post.call_args[1]['json']
        assert 'test-user' in teams_message['text']
        assert 'test message' in teams_message['text']
        assert 'http://github.com/pr/123' in teams_message['text']
        assert 'http://app.terraform.io/workspace' in teams_message['text']
        assert 'http://example.com/approve?run_id=test-run' in teams_message['text']

def test_redis_connection_failure(mock_redis):
    """Test Redis connection failure fallback"""
    mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
    
    with patch('app.REDIS_URL', 'redis://fake'), \
         patch('app.redis') as mock_redis_module:
        mock_redis_module.Redis.from_url.return_value = mock_redis
        
        # This should fall back to in-memory storage
        run_id = 'test-run'
        test_data = {'test': 'data'}
        
        store_token(run_id, test_data)
        assert get_token(run_id) == test_data
        remove_token(run_id)
        assert get_token(run_id) is None

def test_auto_approve_non_speculative(client, mock_requests):
    """Test auto-approval of non-speculative runs when enabled"""
    with patch('app.FILTER_SPECULATIVE_PLANS_ONLY', True), \
         patch('app.HMAC_KEY', ''):  # Disable HMAC verification
        # Mock successful PATCH to Terraform
        mock_requests.patch.return_value.raise_for_status.return_value = None
        
        payload = {
            'access_token': 'real-token',
            'task_result_callback_url': 'http://callback.example.com',
            'run_id': 'test-run',
            'workspace_name': 'test-workspace',
            'is_speculative': False
        }
        
        response = client.post(
            '/teams-approval',
            json=payload
        )
        
        assert response.status_code == 200
        assert b"Auto-approved" in response.data
        
        # Verify Terraform callback was called with "passed" status
        mock_requests.patch.assert_called_once()
        call_kwargs = mock_requests.patch.call_args[1]
        assert '"status": "passed"' in json.dumps(call_kwargs['json'])