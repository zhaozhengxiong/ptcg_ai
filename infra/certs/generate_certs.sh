#!/bin/bash
# Generate mTLS certificates for service-to-service authentication
# This script generates self-signed certificates for development/testing

set -e

CERT_DIR="$(cd "$(dirname "$0")" && pwd)"
CA_KEY="$CERT_DIR/ca-key.pem"
CA_CERT="$CERT_DIR/ca-cert.pem"
SERVER_KEY="$CERT_DIR/server-key.pem"
SERVER_CERT="$CERT_DIR/server-cert.pem"
SERVER_CSR="$CERT_DIR/server.csr"
CLIENT_KEY="$CERT_DIR/client-key.pem"
CLIENT_CERT="$CERT_DIR/client-cert.pem"
CLIENT_CSR="$CERT_DIR/client.csr"

# Generate CA key and certificate
if [ ! -f "$CA_KEY" ]; then
    echo "Generating CA key and certificate..."
    openssl genrsa -out "$CA_KEY" 4096
    openssl req -new -x509 -days 365 -key "$CA_KEY" -out "$CA_CERT" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=CA"
fi

# Generate server key and certificate
if [ ! -f "$SERVER_KEY" ]; then
    echo "Generating server key and certificate..."
    openssl genrsa -out "$SERVER_KEY" 4096
    openssl req -new -key "$SERVER_KEY" -out "$SERVER_CSR" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=game-tools-server"
    openssl x509 -req -days 365 -in "$SERVER_CSR" -CA "$CA_CERT" \
        -CAkey "$CA_KEY" -CAcreateserial -out "$SERVER_CERT"
    rm "$SERVER_CSR"
fi

# Generate client key and certificate (for Referee Agent)
if [ ! -f "$CLIENT_KEY" ]; then
    echo "Generating client key and certificate..."
    openssl genrsa -out "$CLIENT_KEY" 4096
    openssl req -new -key "$CLIENT_KEY" -out "$CLIENT_CSR" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=referee-agent"
    openssl x509 -req -days 365 -in "$CLIENT_CSR" -CA "$CA_CERT" \
        -CAkey "$CA_KEY" -CAcreateserial -out "$CLIENT_CERT"
    rm "$CLIENT_CSR"
fi

echo "Certificates generated successfully!"
echo "CA Certificate: $CA_CERT"
echo "Server Certificate: $SERVER_CERT"
echo "Server Key: $SERVER_KEY"
echo "Client Certificate: $CLIENT_CERT"
echo "Client Key: $CLIENT_KEY"

