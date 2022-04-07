# Try and import the modules provides by the wheel plugin.

import certifi

print("cacert.pem location is", certifi.where())

contents = certifi.contents()
print("cacert.pem size is", len(contents))
