# Actualizacion de llama.cpp

Cada instalacion consulta dinamicamente la API oficial de releases de GitHub. Selecciona de forma determinista un ZIP Windows x64 CUDA 12 y, cuando exista, su paquete `cudart` correspondiente. Rechaza CPU, ARM, Vulkan, HIP, SYCL, OpenVINO y CUDA 13 en esta primera version.

El ZIP se extrae en `runtime/llama_cpp_new`, se valida con `llama-server.exe --version` y solo entonces sustituye `runtime/llama_cpp`. La instalacion anterior se mueve a `runtime/backups`; un fallo conserva el runtime funcional previo.
