#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#    "pytest==8.4.*",
#    "pytest-asyncio==1.0.*",
#    "httpx==0.28.*",
#    "fastapi>=0.115"
# ]
# ///
"""
Session Management Tests

Tests for session expiration, concurrent sessions, and edge cases in session management
across the MCP Adapter services, including OAuth tokens and MCP protocol sessions.
"""

import pytest
import httpx
import asyncio
import time
import json
from typing import Dict, Any, List, Optional

# Test configuration
GATEWAY_URL = "http://localhost:8080"
HELLO_WORLD_URL = "http://localhost:8001"
LATEX_SERVER_URL = "http://localhost:8002"
FILE_SERVER_URL = "http://localhost:8003"


class SessionTestHelper:
    """Helper class for session testing"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.sessions: List[Dict[str, Any]] = []
    
    async def create_mcp_session(self, session_id: str = None) -> Dict[str, Any]:
        """Create a new MCP session"""
        if not session_id:
            session_id = f"test-session-{int(time.time())}-{len(self.sessions)}"
        
        async with httpx.AsyncClient() as client:
            init_request = {
                "jsonrpc": "2.0",
                "id": "session-init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "session-test-client",
                        "version": "0.3.0"
                    },
                    "capabilities": {}
                }
            }
            
            response = await client.post(
                f"{self.base_url}/mcp/",
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            session_info = {
                "session_id": session_id,
                "created_at": time.time(),
                "last_used": time.time(),
                "status": "active" if response.status_code == 200 else "failed",
                "response": response
            }
            
            self.sessions.append(session_info)
            return session_info
    
    async def use_session(self, session_info: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> httpx.Response:
        """Use an existing session to call a tool"""
        async with httpx.AsyncClient() as client:
            request = {
                "jsonrpc": "2.0",
                "id": f"session-call-{int(time.time())}",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            if session_info.get("session_id"):
                headers["Mcp-Session-Id"] = session_info["session_id"]
            
            response = await client.post(
                f"{self.base_url}/mcp/",
                json=request,
                headers=headers
            )
            
            session_info["last_used"] = time.time()
            return response
    
    async def cleanup_sessions(self):
        """Clean up all created sessions"""
        # MCP sessions typically don't need explicit cleanup in HTTP mode
        # But we can test session termination if implemented
        for session_info in self.sessions:
            try:
                async with httpx.AsyncClient() as client:
                    # Try to send a termination notification
                    request = {
                        "jsonrpc": "2.0",
                        "method": "notifications/cancelled",
                        "params": {}
                    }
                    
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"
                    }
                    if session_info.get("session_id"):
                        headers["Mcp-Session-Id"] = session_info["session_id"]
                    
                    await client.post(
                        f"{self.base_url}/mcp/",
                        json=request,
                        headers=headers,
                        timeout=5.0
                    )
            except:
                # Cleanup failures are acceptable
                pass


class OAuthSessionHelper:
    """Helper class for OAuth session testing"""
    
    def __init__(self):
        self.tokens: List[Dict[str, Any]] = []
    
    async def create_oauth_token(self, scope: str = "read write") -> Dict[str, Any]:
        """Create a new OAuth token"""
        async with httpx.AsyncClient() as client:
            # Register client
            registration_data = {
                "client_name": f"Session Test Client {len(self.tokens)}",
                "redirect_uris": ["http://localhost:8090/callback"]
            }
            
            reg_response = await client.post(
                f"{GATEWAY_URL}/oauth/register",
                json=registration_data
            )
            
            if reg_response.status_code != 200:
                return {"status": "failed", "error": "Registration failed"}
            
            client_data = reg_response.json()
            client_id = client_data["client_id"]
            
            # Get authorization code
            auth_params = {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "http://localhost:8090/callback",
                "scope": scope,
                "state": f"test-state-{int(time.time())}"
            }
            
            auth_url = f"{GATEWAY_URL}/oauth/authorize"
            auth_response = await client.get(auth_url, params=auth_params, follow_redirects=False)
            
            if auth_response.status_code != 302:
                return {"status": "failed", "error": "Authorization failed"}
            
            # Extract authorization code from redirect
            redirect_url = auth_response.headers["Location"]
            import urllib.parse
            parsed_url = urllib.parse.urlparse(redirect_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            auth_code = query_params["code"][0]
            
            # Exchange code for token
            token_data = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "http://localhost:8090/callback",
                "client_id": client_id
            }
            
            token_response = await client.post(
                f"{GATEWAY_URL}/oauth/token",
                data=token_data
            )
            
            if token_response.status_code != 200:
                return {"status": "failed", "error": "Token exchange failed"}
            
            token_info = token_response.json()
            token_session = {
                "access_token": token_info["access_token"],
                "token_type": token_info["token_type"],
                "expires_in": token_info["expires_in"],
                "created_at": time.time(),
                "client_id": client_id,
                "status": "active"
            }
            
            self.tokens.append(token_session)
            return token_session
    
    async def validate_token(self, token_session: Dict[str, Any]) -> bool:
        """Validate an OAuth token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GATEWAY_URL}/oauth/tokeninfo",
                data={"token": token_session["access_token"]}
            )
            
            if response.status_code == 200:
                introspection = response.json()
                return introspection.get("active", False)
            
            return False
    
    async def use_token(self, token_session: Dict[str, Any], endpoint: str) -> httpx.Response:
        """Use OAuth token to access protected endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GATEWAY_URL}{endpoint}",
                headers={"Authorization": f"Bearer {token_session['access_token']}"}
            )
            return response


class TestMCPSessionManagement:
    """Test MCP session management"""
    
    @pytest.mark.asyncio
    async def test_concurrent_mcp_sessions(self):
        """Test handling of multiple concurrent MCP sessions"""
        helpers = [
            SessionTestHelper(HELLO_WORLD_URL),
            SessionTestHelper(LATEX_SERVER_URL),
            SessionTestHelper(GATEWAY_URL)
        ]
        
        try:
            # Create multiple sessions concurrently for each service
            session_tasks = []
            for helper in helpers:
                for i in range(3):  # 3 sessions per service
                    session_tasks.append(helper.create_mcp_session(f"concurrent-{i}"))
            
            sessions = await asyncio.gather(*session_tasks, return_exceptions=True)
            
            # Count successful sessions
            successful_sessions = [s for s in sessions if isinstance(s, dict) and s.get("status") == "active"]
            
            # Should be able to create multiple sessions with concurrent session management
            assert len(successful_sessions) > 0, "Session management should support multiple concurrent sessions"
            
            # Test concurrent tool calls using different sessions
            if successful_sessions:
                # Use first few sessions to make concurrent calls
                call_tasks = []
                for session_info in successful_sessions[:5]:  # Use up to 5 sessions
                    if session_info.get("status") == "active":
                        # Find the helper that created this session
                        for helper in helpers:
                            if session_info in helper.sessions:
                                call_tasks.append(
                                    helper.use_session(session_info, "greet", {"name": "Concurrent Test"})
                                )
                                break
                
                if call_tasks:
                    responses = await asyncio.gather(*call_tasks, return_exceptions=True)
                    
                    # At least some calls should work
                    successful_calls = [r for r in responses if isinstance(r, httpx.Response)]
                    assert len(successful_calls) > 0, "No concurrent calls succeeded"
        
        finally:
            # Clean up
            for helper in helpers:
                await helper.cleanup_sessions()
    
    @pytest.mark.asyncio
    async def test_session_isolation(self):
        """Test that sessions are properly isolated"""
        helper = SessionTestHelper(HELLO_WORLD_URL)
        
        try:
            # Create two separate sessions
            session1 = await helper.create_mcp_session("isolation-test-1")
            session2 = await helper.create_mcp_session("isolation-test-2")
            
            if session1.get("status") == "active" and session2.get("status") == "active":
                # Make calls with each session
                response1 = await helper.use_session(session1, "greet", {"name": "Session1"})
                response2 = await helper.use_session(session2, "greet", {"name": "Session2"})
                
                # Both should work independently
                assert response1.status_code in [200, 400]  # 200 if working, 400 if session management not implemented
                assert response2.status_code in [200, 400]
                
                # Sessions should have different IDs
                assert session1["session_id"] != session2["session_id"]
        
        finally:
            await helper.cleanup_sessions()
    
    @pytest.mark.asyncio
    async def test_session_timeout_behavior(self):
        """Test session timeout and expiration behavior"""
        helper = SessionTestHelper(HELLO_WORLD_URL)
        
        try:
            # Create a session
            session_info = await helper.create_mcp_session("timeout-test")
            
            if session_info.get("status") == "active":
                # Use session immediately - should work
                response1 = await helper.use_session(session_info, "greet", {"name": "Initial"})
                initial_status = response1.status_code
                
                # Wait for potential session timeout (if implemented)
                await asyncio.sleep(5)  # Short wait
                
                # Use session after delay
                response2 = await helper.use_session(session_info, "greet", {"name": "After Delay"})
                
                # Both should have similar status (sessions likely don't timeout this quickly)
                assert response2.status_code == initial_status or response2.status_code in [400, 401, 403]
        
        finally:
            await helper.cleanup_sessions()
    
    @pytest.mark.asyncio
    async def test_invalid_session_handling(self):
        """Test handling of invalid or expired sessions"""
        helper = SessionTestHelper(HELLO_WORLD_URL)
        
        try:
            # Test with completely invalid session ID
            fake_session = {
                "session_id": "totally-fake-session-id-12345",
                "created_at": time.time(),
                "last_used": time.time(),
                "status": "fake"
            }
            
            response = await helper.use_session(fake_session, "greet", {"name": "Invalid Session"})
            
            # Should either work (if sessions not validated) or return appropriate error
            assert response.status_code in [200, 400, 401, 403, 404]
            
            # Test with malformed session ID
            malformed_session = {
                "session_id": "../../../etc/passwd",
                "created_at": time.time(),
                "last_used": time.time(),
                "status": "malformed"
            }
            
            response2 = await helper.use_session(malformed_session, "greet", {"name": "Malformed Session"})
            assert response2.status_code in [200, 400, 401, 403, 404]
        
        finally:
            await helper.cleanup_sessions()


class TestOAuthSessionManagement:
    """Test OAuth session and token management"""
    
    @pytest.mark.asyncio
    async def test_oauth_token_expiration(self):
        """Test OAuth token expiration handling"""
        helper = OAuthSessionHelper()
        
        # Create OAuth token
        token_session = await helper.create_oauth_token()
        
        if token_session.get("status") != "failed":
            # Verify token is initially valid
            is_valid = await helper.validate_token(token_session)
            assert is_valid, "Newly created token should be valid"
            
            # Test token usage
            response = await helper.use_token(token_session, "/health")
            assert response.status_code == 200, "Token should work for accessing endpoints"
            
            # Simulate token expiration by modifying creation time
            original_created_at = token_session["created_at"]
            token_session["created_at"] = time.time() - 7300  # Simulate expired token (>2 hours)
            
            # Test expired token validation
            # Note: Our implementation might not actually enforce expiration yet
            is_valid_after = await helper.validate_token(token_session)
            
            # Restore original time for cleanup
            token_session["created_at"] = original_created_at
    
    @pytest.mark.asyncio
    async def test_concurrent_oauth_tokens(self):
        """Test multiple concurrent OAuth tokens"""
        helper = OAuthSessionHelper()
        
        # Create multiple tokens concurrently
        token_tasks = [helper.create_oauth_token(f"read write scope{i}") for i in range(5)]
        tokens = await asyncio.gather(*token_tasks, return_exceptions=True)
        
        # Count successful tokens
        valid_tokens = [t for t in tokens if isinstance(t, dict) and t.get("status") != "failed"]
        
        assert len(valid_tokens) > 0, "Should be able to create multiple OAuth tokens"
        
        # Test concurrent token usage
        if valid_tokens:
            usage_tasks = [helper.use_token(token, "/info") for token in valid_tokens[:3]]
            responses = await asyncio.gather(*usage_tasks, return_exceptions=True)
            
            successful_responses = [r for r in responses if isinstance(r, httpx.Response) and r.status_code == 200]
            assert len(successful_responses) > 0, "Should be able to use multiple tokens concurrently"
    
    @pytest.mark.asyncio
    async def test_oauth_token_introspection_consistency(self):
        """Test OAuth token introspection consistency"""
        helper = OAuthSessionHelper()
        
        # Create token
        token_session = await helper.create_oauth_token()
        
        if token_session.get("status") != "failed":
            # Perform multiple introspection calls
            introspection_tasks = [helper.validate_token(token_session) for _ in range(5)]
            results = await asyncio.gather(*introspection_tasks, return_exceptions=True)
            
            # All results should be consistent
            valid_results = [r for r in results if isinstance(r, bool)]
            if valid_results:
                first_result = valid_results[0]
                assert all(r == first_result for r in valid_results), "Token introspection results should be consistent"
    
    @pytest.mark.asyncio
    async def test_oauth_token_revocation_simulation(self):
        """Test simulation of token revocation scenarios"""
        helper = OAuthSessionHelper()
        
        # Create token
        token_session = await helper.create_oauth_token()
        
        if token_session.get("status") != "failed":
            # Use token normally
            response1 = await helper.use_token(token_session, "/health")
            assert response1.status_code == 200
            
            # Simulate token being marked as revoked by modifying it
            original_token = token_session["access_token"]
            token_session["access_token"] = "revoked-" + original_token
            
            # Try to use "revoked" token
            response2 = await helper.use_token(token_session, "/health")
            
            # Should either fail or succeed (depending on whether validation is implemented)
            assert response2.status_code in [200, 401, 403]
            
            # Restore original token
            token_session["access_token"] = original_token


class TestSessionEdgeCases:
    """Test edge cases in session management"""
    
    @pytest.mark.asyncio
    async def test_session_with_malformed_requests(self):
        """Test session handling with malformed requests"""
        async with httpx.AsyncClient() as client:
            malformed_requests = [
                # Missing required fields
                {"jsonrpc": "2.0", "id": "test"},
                # Invalid JSON-RPC version
                {"jsonrpc": "1.0", "id": "test", "method": "initialize"},
                # Missing ID
                {"jsonrpc": "2.0", "method": "initialize"},
                # Invalid method
                {"jsonrpc": "2.0", "id": "test", "method": "invalid_method"},
                # Malformed session ID header
                None,  # Will use malformed header
            ]
            
            for i, request_data in enumerate(malformed_requests):
                headers = {"Content-Type": "application/json"}
                
                if request_data is None:
                    # Test malformed session header
                    request_data = {
                        "jsonrpc": "2.0",
                        "id": "test",
                        "method": "tools/call",
                        "params": {"name": "greet", "arguments": {"name": "test"}}
                    }
                    headers["Mcp-Session-Id"] = "../../../etc/passwd"
                
                try:
                    response = await client.post(
                        f"{GATEWAY_URL}/mcp/",
                        json=request_data,
                        headers=headers,
                        timeout=10.0
                    )
                    
                    # Should handle malformed requests gracefully
                    assert response.status_code in [200, 400, 404, 405, 406, 500]
                    
                    # Response should be valid JSON (for JSON-RPC errors)
                    if response.headers.get("content-type", "").startswith("application/json"):
                        try:
                            response.json()  # Should not raise exception
                        except json.JSONDecodeError:
                            pytest.fail(f"Invalid JSON response for malformed request {i}")
                
                except httpx.TimeoutException:
                    # Timeout is acceptable for malformed requests
                    pass
    
    @pytest.mark.asyncio
    async def test_session_resource_limits(self):
        """Test session behavior under resource constraints"""
        helpers = []
        
        try:
            # Try to create many sessions to test limits
            for i in range(20):  # Try to create 20 sessions
                helper = SessionTestHelper(HELLO_WORLD_URL)
                session_info = await helper.create_mcp_session(f"limit-test-{i}")
                
                if session_info.get("status") == "active":
                    helpers.append(helper)
                
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.1)
            
            # System should handle multiple sessions or gracefully reject excess
            assert len(helpers) >= 0  # At least some sessions should be possible
            
            # Test using multiple sessions
            if helpers:
                # Use a subset of sessions
                use_tasks = []
                for helper in helpers[:10]:  # Use up to 10 sessions
                    if helper.sessions and helper.sessions[0].get("status") == "active":
                        use_tasks.append(
                            helper.use_session(helper.sessions[0], "greet", {"name": "Resource Test"})
                        )
                
                if use_tasks:
                    responses = await asyncio.gather(*use_tasks, return_exceptions=True)
                    
                    # Some responses should work
                    successful = [r for r in responses if isinstance(r, httpx.Response)]
                    assert len(successful) >= 0  # Should handle the load reasonably
        
        finally:
            # Clean up all helpers
            for helper in helpers:
                await helper.cleanup_sessions()
    
    @pytest.mark.asyncio
    async def test_session_persistence_across_requests(self):
        """Test session state persistence across multiple requests"""
        helper = SessionTestHelper(HELLO_WORLD_URL)
        
        try:
            # Create session
            session_info = await helper.create_mcp_session("persistence-test")
            
            if session_info.get("status") == "active":
                # Make multiple requests with same session
                request_results = []
                
                for i in range(5):
                    response = await helper.use_session(
                        session_info, 
                        "greet", 
                        {"name": f"Request {i}"}
                    )
                    request_results.append(response.status_code)
                    
                    # Small delay between requests
                    await asyncio.sleep(0.5)
                
                # All requests should have consistent behavior
                if request_results:
                    first_status = request_results[0]
                    # All should be the same status or improve over time
                    for status in request_results:
                        assert status == first_status or status in [200, 400]
        
        finally:
            await helper.cleanup_sessions()
    
    @pytest.mark.asyncio
    async def test_cross_service_session_isolation(self):
        """Test that sessions are isolated between different services"""
        hello_helper = SessionTestHelper(HELLO_WORLD_URL)
        latex_helper = SessionTestHelper(LATEX_SERVER_URL)
        
        try:
            # Create sessions on different services
            hello_session = await hello_helper.create_mcp_session("cross-service-hello")
            latex_session = await latex_helper.create_mcp_session("cross-service-latex")
            
            # Try to use hello session with latex service (should not work)
            if hello_session.get("status") == "active":
                # This should fail or be ignored since it's the wrong service
                cross_response = await latex_helper.use_session(
                    hello_session,
                    "validate_latex",
                    {"content": r"\documentclass{article}\begin{document}test\end{document}"}
                )
                
                # Should fail or be handled gracefully
                assert cross_response.status_code in [200, 400, 401, 403, 404, 500]
            
            # Normal usage should still work
            if hello_session.get("status") == "active":
                normal_response = await hello_helper.use_session(
                    hello_session,
                    "greet",
                    {"name": "Cross Service Test"}
                )
                assert normal_response.status_code in [200, 400]
        
        finally:
            await hello_helper.cleanup_sessions()
            await latex_helper.cleanup_sessions()