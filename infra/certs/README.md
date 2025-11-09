# mTLS Certificates

This directory contains scripts and certificates for mutual TLS authentication between services.

## Generating Certificates

Run the certificate generation script:

```bash
./generate_certs.sh
```

This will create:
- `ca-cert.pem` - Certificate Authority certificate
- `ca-key.pem` - Certificate Authority private key
- `server-cert.pem` - Server certificate (for Game Tools service)
- `server-key.pem` - Server private key
- `client-cert.pem` - Client certificate (for Referee Agent)
- `client-key.pem` - Client private key

## Usage

These certificates are used for:
- Game Tools gRPC service (server)
- Referee Agent (client)

The certificates are self-signed and suitable for development/testing. For production, use certificates from a proper CA.

## Security Notes

- Keep private keys secure and never commit them to version control
- Add `*.pem` and `*.key` to `.gitignore`
- Rotate certificates regularly in production

