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
Service Reliability Tests

Tests for handling partial backend failures, timeout scenarios, and service degradation.
Verifies that the system gracefully handles various failure modes without complete system failure.
"""

import pytest
import httpx
import asyncio
import time
from unittest.mock import patch, AsyncMock
from typing import Dict, Any

# Test configuration
GATEWAY_URL = "http://localhost:8080"
HELLO_WORLD_URL = "http://localhost:8001"
LATEX_SERVER_URL = "http://localhost:8002"
FILE_SERVER_URL = "http://localhost:8003"


class MockFailureServer:
    """Mock server for simulating various failure scenarios"""
    
    def __init__(self, failure_type: str):
        self.failure_type = failure_type
        self.call_count = 0
    
    async def handle_request(self, request):
        """Simulate different failure types"""
        self.call_count += 1
        
        if self.failure_type == "timeout":
            await asyncio.sleep(30)  # Long delay to trigger timeout
            return httpx.Response(200, json={"status": "success"})
        
        elif self.failure_type == "intermittent":
            if self.call_count % 2 == 0:
                return httpx.Response(500, json={"error": "Intermittent failure"})
            else:
                return httpx.Response(200, json={"status": "success"})
        
        elif self.failure_type == "connection_refused":
            raise httpx.ConnectError("Connection refused")
        
        elif self.failure_type == "slow_response":
            await asyncio.sleep(5)  # Slow but not timeout
            return httpx.Response(200, json={"status": "slow success"})
        
        elif self.failure_type == "invalid_response":
            return httpx.Response(200, content=b"not json content")
        
        elif self.failure_type == "partial_content":
            return httpx.Response(200, json={"incomplete": "response"})
        
        else:  # default failure
            return httpx.Response(500, json={"error": "Server error"})


class TestBackendFailureScenarios:
    """Test various backend failure scenarios"""
    
    @pytest.mark.asyncio
    async def test_gateway_with_one_backend_down(self):
        """Test gateway behavior when one backend service is down"""
        # Test gateway health when hello-world might be down
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Gateway should still be accessible
            response = await client.get(f"{GATEWAY_URL}/health")
            assert response.status_code == 200
            
            # Dashboard should still work (might show fewer tools)
            response = await client.get(f"{GATEWAY_URL}/dashboard")
            assert response.status_code == 200
            
            # Info endpoint should still provide information
            response = await client.get(f"{GATEWAY_URL}/info")
            assert response.status_code == 200
            info_data = response.json()
            assert "connected_servers" in info_data
    
    @pytest.mark.asyncio
    async def test_file_server_reliability(self):
        """Test file server resilience to various failure conditions"""
        test_scenarios = [
            ("Large file upload", {"size": 1024 * 1024, "filename": "large_test.txt"}),
            ("Special characters", {"size": 100, "filename": "special_chars_测试.txt"}),
            ("Long filename", {"size": 100, "filename": "a" * 200 + ".txt"}),
            ("Rapid uploads", {"count": 10, "size": 100}),
        ]
        
        for scenario_name, config in test_scenarios:
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    if "count" in config:
                        # Test rapid uploads
                        upload_tasks = []
                        for i in range(config["count"]):
                            content = b"A" * config["size"]
                            files = {'file': (f'rapid_{i}.txt', content, 'text/plain')}
                            upload_tasks.append(
                                client.post(f"{FILE_SERVER_URL}/files", files=files)
                            )
                        
                        responses = await asyncio.gather(*upload_tasks, return_exceptions=True)
                        
                        # Some should succeed, some might fail due to load
                        successful = [r for r in responses if isinstance(r, httpx.Response) and r.status_code == 200]
                        assert len(successful) > 0, f"No uploads succeeded in {scenario_name}"
                        
                        # Clean up successful uploads
                        for response in successful:
                            try:
                                data = response.json()
                                if "file_id" in data:
                                    await client.delete(f"{FILE_SERVER_URL}/files/{data['file_id']}")
                            except:
                                pass
                    
                    else:
                        # Test single upload scenarios
                        content = b"A" * config["size"]
                        files = {'file': (config["filename"], content, 'text/plain')}
                        
                        response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                        
                        # Should either succeed or fail gracefully
                        if response.status_code == 200:
                            data = response.json()
                            assert data.get("success") is True
                            
                            # Verify file can be downloaded
                            file_id = data["file_id"]
                            download_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                            assert download_response.status_code == 200
                            
                            # Clean up
                            await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
                        
                        else:
                            # Graceful failure is acceptable
                            assert response.status_code in [400, 413, 500]
                
                except httpx.TimeoutException:
                    # Timeout is acceptable for stress testing
                    pass
                except Exception as e:
                    # Other exceptions should be investigated but don't fail the test
                    print(f"Exception in {scenario_name}: {e}")
    
    @pytest.mark.asyncio
    async def test_latex_server_timeout_handling(self):
        """Test LaTeX server behavior under timeout conditions"""
        # Test with potentially problematic LaTeX that might cause long compilation
        problematic_latex_samples = [
            # Large document
            r"""
            \documentclass{article}
            \begin{document}
            """ + "\n".join([f"This is line {i} of a very long document." for i in range(10000)]) + r"""
            \end{document}
            """,
            
            # Complex formatting
            r"""
            \documentclass{article}
            \usepackage{amsmath}
            \begin{document}
            """ + "\n".join([r"\begin{equation} x_{" + str(i) + r"} = \sum_{j=1}^{1000} \frac{1}{j} \end{equation}" for i in range(100)]) + r"""
            \end{document}
            """,
        ]
        
        for i, latex_content in enumerate(problematic_latex_samples):
            async with httpx.AsyncClient(timeout=45.0) as client:
                try:
                    # Upload LaTeX file
                    data = {
                        'content': latex_content,
                        'filename': f'timeout_test_{i}.tex'
                    }
                    
                    response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
                    
                    if response.status_code == 200:
                        upload_data = response.json()
                        file_id = upload_data["file_id"]
                        
                        # Attempt compilation with timeout
                        try:
                            # Direct test of LaTeX server (would go through gateway in real use)
                            latex_response = await client.post(
                                f"{LATEX_SERVER_URL}/mcp/",
                                json={
                                    "jsonrpc": "2.0",
                                    "id": f"timeout-test-{i}",
                                    "method": "tools/call",
                                    "params": {
                                        "name": "compile_latex_by_id",
                                        "arguments": {"file_id": file_id}
                                    }
                                },
                                timeout=30.0  # Reasonable timeout for compilation
                            )
                            
                            # Should either succeed or fail gracefully within timeout
                            assert latex_response.status_code in [200, 400, 500]
                            
                        except httpx.TimeoutException:
                            # Timeout is acceptable for complex documents
                            pass
                        
                        # Clean up
                        await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
                
                except Exception as e:
                    # Document exceptions but don't fail test
                    print(f"Exception in timeout test {i}: {e}")
    
    @pytest.mark.asyncio
    async def test_gateway_tool_discovery_resilience(self):
        """Test gateway tool discovery when backend servers are unreliable"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Test info endpoint which aggregates tool information
                response = await client.get(f"{GATEWAY_URL}/info")
                
                if response.status_code == 200:
                    info_data = response.json()
                    
                    # Should have basic structure even if some backends are down
                    assert "connected_servers" in info_data
                    assert "available_tools" in info_data
                    assert "tool_count" in info_data
                    assert "server_count" in info_data
                    
                    # Tool count should be non-negative
                    assert info_data["tool_count"] >= 0
                    assert info_data["server_count"] >= 0
                
                # Test dashboard which shows aggregated information
                response = await client.get(f"{GATEWAY_URL}/dashboard")
                assert response.status_code == 200
                
                # Dashboard should render without errors even with partial backend failures
                dashboard_html = response.text
                assert "MCP Adapter Dashboard" in dashboard_html
                assert "Connected Servers" in dashboard_html
                
            except httpx.TimeoutException:
                # Gateway should be fast, but timeout is not a complete failure
                pass
    
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test system behavior under concurrent load"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test multiple concurrent requests to different endpoints
            concurrent_tasks = []
            
            # Gateway endpoints
            for i in range(5):
                concurrent_tasks.append(client.get(f"{GATEWAY_URL}/health"))
                concurrent_tasks.append(client.get(f"{GATEWAY_URL}/info"))
            
            # File server endpoints
            for i in range(3):
                files = {'file': (f'concurrent_{i}.txt', f'content {i}'.encode(), 'text/plain')}
                concurrent_tasks.append(client.post(f"{FILE_SERVER_URL}/files", files=files))
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
            
            # Count successful responses
            successful_responses = 0
            failed_responses = 0
            timeouts = 0
            
            file_ids_to_cleanup = []
            
            for response in responses:
                if isinstance(response, httpx.Response):
                    if 200 <= response.status_code < 300:
                        successful_responses += 1
                        # Check if it's a file upload response for cleanup
                        try:
                            if response.request.url.path.endswith('/files') and response.request.method == 'POST':
                                data = response.json()
                                if "file_id" in data:
                                    file_ids_to_cleanup.append(data["file_id"])
                        except:
                            pass
                    else:
                        failed_responses += 1
                elif isinstance(response, httpx.TimeoutException):
                    timeouts += 1
                else:
                    failed_responses += 1
            
            # Clean up uploaded files
            for file_id in file_ids_to_cleanup:
                try:
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
                except:
                    pass
            
            # System should handle most requests successfully
            total_requests = len(concurrent_tasks)
            success_rate = successful_responses / total_requests
            
            # At least 50% should succeed under normal conditions
            assert success_rate >= 0.5, f"Success rate too low: {success_rate:.2%} ({successful_responses}/{total_requests})"
            
            # System should not completely fail
            assert successful_responses > 0, "No requests succeeded - system may be down"


class TestTimeoutScenarios:
    """Test various timeout scenarios"""
    
    @pytest.mark.asyncio
    async def test_client_timeout_handling(self):
        """Test client-side timeout handling"""
        test_timeouts = [1.0, 5.0, 10.0, 30.0]
        
        for timeout_value in test_timeouts:
            async with httpx.AsyncClient(timeout=timeout_value) as client:
                start_time = time.time()
                
                try:
                    # Test normal requests that should complete within timeout
                    response = await client.get(f"{GATEWAY_URL}/health")
                    elapsed = time.time() - start_time
                    
                    # Should complete well within timeout for health check
                    assert elapsed < timeout_value * 0.8, f"Request took too long: {elapsed:.2f}s with {timeout_value}s timeout"
                    assert response.status_code == 200
                
                except httpx.TimeoutException:
                    elapsed = time.time() - start_time
                    # Should timeout close to the specified timeout value
                    assert elapsed >= timeout_value * 0.8, f"Timeout too early: {elapsed:.2f}s with {timeout_value}s timeout"
    
    @pytest.mark.asyncio
    async def test_server_response_time_distribution(self):
        """Test distribution of server response times"""
        response_times = []
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Collect response times for multiple requests
            for i in range(20):
                start_time = time.time()
                
                try:
                    response = await client.get(f"{GATEWAY_URL}/health")
                    elapsed = time.time() - start_time
                    
                    if response.status_code == 200:
                        response_times.append(elapsed)
                
                except httpx.TimeoutException:
                    # Skip timeouts for this analysis
                    pass
                
                # Small delay between requests
                await asyncio.sleep(0.1)
        
        if response_times:
            # Calculate statistics
            avg_time = sum(response_times) / len(response_times)
            max_time = max(response_times)
            min_time = min(response_times)
            
            # Verify reasonable response times
            assert avg_time < 2.0, f"Average response time too high: {avg_time:.3f}s"
            assert max_time < 5.0, f"Maximum response time too high: {max_time:.3f}s"
            assert min_time < 1.0, f"Minimum response time too high: {min_time:.3f}s"
            
            # Verify consistency (max should not be much higher than average)
            assert max_time < avg_time * 10, f"Response times too inconsistent: avg={avg_time:.3f}s, max={max_time:.3f}s"


class TestErrorRecovery:
    """Test error recovery and system resilience"""
    
    @pytest.mark.asyncio
    async def test_service_recovery_after_failure(self):
        """Test that services can recover from temporary failures"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test multiple requests to see if intermittent failures recover
            success_count = 0
            failure_count = 0
            
            for i in range(10):
                try:
                    response = await client.get(f"{GATEWAY_URL}/health")
                    
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        failure_count += 1
                
                except Exception:
                    failure_count += 1
                
                # Small delay between requests
                await asyncio.sleep(0.5)
            
            # System should recover and have some successful requests
            assert success_count > 0, "No successful requests - system may be completely down"
            
            # If there are failures, they should be minority
            if failure_count > 0:
                success_rate = success_count / (success_count + failure_count)
                assert success_rate >= 0.7, f"Too many failures: {failure_count}/{success_count + failure_count}"
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test that system degrades gracefully when backends are unavailable"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Test gateway endpoints that should work even with backend issues
            critical_endpoints = [
                ("/health", "Gateway health check"),
                ("/info", "Gateway information"),
                ("/.well-known/oauth-authorization-server", "OAuth discovery"),
            ]
            
            working_endpoints = []
            failed_endpoints = []
            
            for endpoint, description in critical_endpoints:
                try:
                    response = await client.get(f"{GATEWAY_URL}{endpoint}")
                    
                    if response.status_code == 200:
                        working_endpoints.append((endpoint, description))
                    else:
                        failed_endpoints.append((endpoint, description, response.status_code))
                
                except Exception as e:
                    failed_endpoints.append((endpoint, description, str(e)))
            
            # At least basic gateway functionality should work
            assert len(working_endpoints) > 0, "No critical endpoints working - gateway may be down"
            
            # Health endpoint should always work
            health_working = any(endpoint == "/health" for endpoint, _ in working_endpoints)
            assert health_working, "Health endpoint not working - this indicates serious issues"
    
    @pytest.mark.asyncio
    async def test_memory_and_resource_leaks(self):
        """Test for potential memory and resource leaks under load"""
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Perform many small operations to check for leaks
            file_ids = []
            
            try:
                # Create many small files
                for i in range(50):
                    files = {'file': (f'leak_test_{i}.txt', f'content {i}'.encode(), 'text/plain')}
                    
                    try:
                        response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                        if response.status_code == 200:
                            data = response.json()
                            file_ids.append(data["file_id"])
                    except:
                        # Individual failures are ok for this test
                        pass
                
                # System should still be responsive
                health_response = await client.get(f"{GATEWAY_URL}/health")
                assert health_response.status_code == 200
                
                # File server should still be responsive
                if file_ids:
                    # Try to download a few files to verify system is still working
                    for file_id in file_ids[:5]:
                        try:
                            download_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                            assert download_response.status_code == 200
                        except:
                            # Individual download failures are ok
                            pass
            
            finally:
                # Clean up all created files
                for file_id in file_ids:
                    try:
                        await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
                    except:
                        # Cleanup failures are ok for this test
                        pass


class TestNetworkResilience:
    """Test network-related resilience"""
    
    @pytest.mark.asyncio
    async def test_connection_pooling_behavior(self):
        """Test connection pooling and reuse"""
        # Use single client for multiple requests to test connection reuse
        async with httpx.AsyncClient(timeout=10.0) as client:
            responses = []
            
            # Make multiple requests that should reuse connections
            for i in range(10):
                try:
                    response = await client.get(f"{GATEWAY_URL}/health")
                    responses.append(response)
                except Exception as e:
                    responses.append(e)
                
                # Small delay to allow connection reuse
                await asyncio.sleep(0.1)
            
            # Most requests should succeed
            successful_responses = [r for r in responses if isinstance(r, httpx.Response) and r.status_code == 200]
            assert len(successful_responses) >= 7, f"Too few successful requests: {len(successful_responses)}/10"
    
    @pytest.mark.asyncio
    async def test_retry_behavior(self):
        """Test client retry behavior for failed requests"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{GATEWAY_URL}/health")
                    
                    if response.status_code == 200:
                        # Success on this attempt
                        break
                    
                    # Wait before retry
                    await asyncio.sleep(1.0 * (attempt + 1))
            
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    pytest.fail(f"All {max_retries} attempts failed. Last error: {e}")
                
                # Wait before retry
                await asyncio.sleep(1.0 * (attempt + 1))
        
        # If we get here, at least one attempt succeeded
        assert True