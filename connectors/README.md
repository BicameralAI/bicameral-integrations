# Connectors

Connectors are provider-facing components. They know external APIs, auth flows,
pagination, retries, webhook signatures, and provider-native ids.

Connectors return raw or lightly structured provider observations. The universal
adapter turns those observations into Bicameral emissions.
