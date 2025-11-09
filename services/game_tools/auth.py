"""Authentication middleware for Game Tools service."""
from __future__ import annotations

import logging
from typing import Optional

import grpc

logger = logging.getLogger(__name__)


class AuthInterceptor(grpc.ServerInterceptor):
    """gRPC interceptor for authentication using mTLS and tokens."""

    def __init__(self, allowed_referee_ids: list[str], token_secret: Optional[str] = None):
        """Initialize auth interceptor.
        
        Args:
            allowed_referee_ids: List of referee IDs allowed to call the service
            token_secret: Secret for token validation (optional for now)
        """
        self.allowed_referee_ids = set(allowed_referee_ids)
        self.token_secret = token_secret

    def intercept_service(self, continuation, handler_call_details):
        """Intercept service calls to validate authentication."""
        metadata = dict(handler_call_details.invocation_metadata)
        
        # Check for referee ID in metadata
        referee_id = metadata.get("referee-id")
        if not referee_id:
            logger.warning("元数据中缺少 referee-id")
            return self._reject_call(grpc.StatusCode.UNAUTHENTICATED, "Missing referee-id")
        
        if referee_id not in self.allowed_referee_ids:
            logger.warning(f"未授权的 referee-id: {referee_id}")
            return self._reject_call(grpc.StatusCode.PERMISSION_DENIED, "Unauthorized referee")
        
        # TODO: Add token validation when token_secret is provided
        # For now, we rely on mTLS for service-to-service auth
        
        return continuation(handler_call_details)

    @staticmethod
    def _reject_call(status_code: grpc.StatusCode, details: str):
        """Reject the call with given status and details."""
        def _reject(continuation, handler_call_details):
            return grpc.unary_unary_rpc_method_handler(
                lambda request, context: context.abort(status_code, details)
            )
        return _reject


def validate_referee_token(token: str, secret: Optional[str]) -> bool:
    """Validate a referee token.
    
    Args:
        token: Token to validate
        secret: Secret key for validation
        
    Returns:
        True if token is valid, False otherwise
    """
    if not secret:
        # If no secret configured, skip token validation (rely on mTLS)
        return True
    
    # TODO: Implement JWT or similar token validation
    # For now, return True as placeholder
    return True


def create_secure_channel(
    target: str,
    ca_cert_path: str,
    client_cert_path: str,
    client_key_path: str,
) -> grpc.Channel:
    """Create a secure gRPC channel with mTLS.
    
    Args:
        target: Server address (e.g., "localhost:50051")
        ca_cert_path: Path to CA certificate
        client_cert_path: Path to client certificate
        client_key_path: Path to client private key
        
    Returns:
        Secure gRPC channel
    """
    with open(ca_cert_path, "rb") as f:
        ca_cert = f.read()
    
    with open(client_cert_path, "rb") as f:
        client_cert = f.read()
    
    with open(client_key_path, "rb") as f:
        client_key = f.read()
    
    credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_cert,
        private_key=client_key,
        certificate_chain=client_cert,
    )
    
    return grpc.secure_channel(target, credentials)
