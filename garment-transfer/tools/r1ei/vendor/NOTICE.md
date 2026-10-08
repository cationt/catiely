# Vendored: `utils.py` de huan-yin/Easy-Insert (Apache-2.0)

| Campo | Valor |
|---|---|
| Origem | https://github.com/huan-yin/Easy-Insert — arquivo `utils.py` |
| Commit | `82094484f432b74efb6c4ccbf144c08350f02144` (2026-08-16, "update diffusers inference") |
| sha256 do arquivo (byte-idêntico) | `d84f0cbc0a85de804ad1bf65955d6ad0fd213a4b70f9ddc620f898fd54dd300f` |
| Licença | Apache-2.0 (cópia em `LICENSE-Easy-Insert.txt`) |

Por que vendorar: o pré-processamento (recorte quadrado em torno da máscara com `crop_scale=1.2`, redimensionamento para 1024², composição com branco, `paste_back` sem feather) **define** o que o modelo vê. Usar o arquivo byte-idêntico ao upstream elimina uma fonte de divergência; `run_easy_insert.py` confere o sha256 antes de importar (e, se `--easy-insert-dir` apontar para o clone, confere o sha do `utils.py` do clone também). Nenhuma modificação local é permitida neste arquivo.
