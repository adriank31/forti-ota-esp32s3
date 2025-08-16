idf_component_register(
  SRCS "advanced_https_ota_example.c" "ble_helper/bluedroid_gatts.c" "ble_helper/nimble_gatts.c" "ble_helper/ble_api.c"
  INCLUDE_DIRS "." "./ble_helper/include/"
  EMBED_TXTFILES ../server_certs/ca_cert.pem
)
