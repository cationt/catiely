# Revisão adversarial da preparação R2 — 2026-10-08

Revisão do próprio patch pela implementadora. Escopo: CPU/estático; nenhuma
execução real do servidor, setup, smoke GPU ou benchmark. Não é evidência de H4.

| Risco examinado | Resultado/evidência |
|---|---|
| Cache warm disfarçando saída repetida | Fecho de A/B calculado do grafo; history/status.messages obrigatório; todos os 11 nós do fecho testados como cache proibido; exit23 e sidecar de cached_result testados. |
| IDs fixos ou ampliação silenciosa | IDs inteiramente renomeados no teste; classes inesperadas e encode sem imagens fora do fecho falham pedindo decisão humana. |
| Patches de modelo indevidamente invalidados | AuraFlow/CFGNorm preservados fora do fecho; decisão aprovada após reprodução CPU no core pinado. |
| Cold/warm trocados | Teste do supervisor simula três servidores novos e três warm no terceiro servidor; nenhuma chamada free/cache-none. Bootstrap exige model manager vazio no startup. |
| Controle positivo do smoke aceito como benchmark | Proibido quando smoke=false; fake HTTP/WS cobre repetição idêntica seguida de aliases renomeados; logs/outputs/identidades permanecem separados. |
| Peso errado, Q3, Lightning ou download | SHA/tamanho/revisão dos três pesos, A/B, core/desktop/GGUF verificados em CPU local; workflow não contém LoRA; setup somente verifica arquivos existentes. |
| Servidor antigo/PID reutilizado/porta alheia | Gate de processo existente e bind exclusivo; PID/create_time/comando/porta checados; testes rejeitam outro proprietário e PID reutilizado. |
| Saída antiga, path traversal, overwrite, run desvinculado | UUIDs, criação exclusiva, prefixo/mtime/PNG metadata, SHA e binding de prompt/grafo/PID/run; fake server rejeita output antigo e parâmetros divergentes; limpeza restrita a aliases próprios. |
| Falha do monitor com exit externo zero | JSON/exit do filho/deadline/verdict/PID/sidecar exigidos. Contratos adversariais e supervisor param no primeiro erro; sem retry/fallback. |
| Watchdog não encerra motor externo | Supervisor encerra somente seu processo/descendentes no finally, preserva sidecar/log incompleto se cliente morrer. Startup fora de measure_run. |
| Alteração interna do histórico quebra comparação | Core acrescenta is_changed; comparação remove somente esse campo interno e preserva todos os parâmetros efetivos. Testado com metadados PNG fake. |
| Runs longos rejeitados por parser de log | Core muda para HH:MM:SS após 600 s; dois formatos testados. Log pode aparecer logo após history; espera limitada de 2 s, fora do wall do sidecar. |
| Rede inesperada | Guardas Python bloqueiam connect/sendto/DNS externos; testes negativos CPU. API nodes/manager desativados, frontend local e somente custom node GGUF. Não se afirma firewall do SO. |
| PS5.1/encoding/OneDrive | Dois scripts ASCII, paths como argumentos; parser real Windows PowerShell5.1 e os dois wrappers em DryRun passaram. Workflows com eol=lf e SHA bruto congelado. |
| Configuração/projeção confundida com resultado | 40 primária; 20 desabilitada; secundária explícita. H4 não é emitida automaticamente; thrashing continua revisão dos dados, sem novo threshold. |

Validação final desta preparação: **41 testes CPU passaram** em
`tests/test_r2_qie.py`, incluindo servidor HTTP/websocket fake com imagens 8×8;
dois dry-runs PS5.1 passaram; conferência integral da provenance local passou.
Template instalado também confere com o Git blob oficial
`e532d3473143202fe40b5cee91c1cff5da92d74a`.

Limites materiais: integração GPU real ainda depende do setup/smoke do operador;
cache sob pressão de RAM pode divergir e será registrado; sampling_s inclui
carga/offload do nó e latência websocket; tree_private não cobre o motor;
nenhum resultado sobre memória, tempo, qualidade ou H4 foi produzido.
