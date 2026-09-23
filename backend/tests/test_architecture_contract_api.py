import uuid

import pytest


@pytest.mark.asyncio
async def test_registration_uses_explicit_application_contract(client):
    suffix = uuid.uuid4().hex[:8]
    csrf = (await client.get('/api/auth/csrf')).json()['csrf_token']
    response = await client.post('/api/auth/register', headers={'X-CSRF-Token': csrf}, json={
        'student_no': f'DTO{suffix}', 'real_name': '响应契约学生',
        'email': f'dto-{suffix}@example.com', 'phone_number': '13800138000',
        'password': 'ValidPassword!123',
    })
    assert response.status_code == 201
    assert set(response.json()['application']) == {
        'id', 'status', 'reason', 'submitted_profile', 'submitted_at', 'reviewed_at', 'reviewer_id',
    }
    schema = (await client.get('/openapi.json')).json()
    success = schema['paths']['/api/auth/register']['post']['responses']['201']
    assert success['content']['application/json']['schema'].get('$ref')
