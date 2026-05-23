---
applyTo: "src/risk/**/*.py"
description: "Risk Engine — autoridade suprema, regras extras de segurança."
---

# Risk Engine — Convenções Críticas

O Risk Engine é o **último ponto de defesa** entre a estratégia e o capital. Bugs aqui causam perda real.

## Regras Inegociáveis

1. **Processo isolado.** O Risk Engine roda em processo separado (`multiprocessing`) e não compartilha event loop com Strategy/OMS.
2. **Sem side-effects implícitos.** Toda decisão (`allow`/`deny`) é determinística dado o estado.
3. **Toda ordem passa por `RiskGate.check_pre_trade()`** antes de chegar ao OMS. Sem exceções.
4. **Halt é unidirecional.** Uma vez triggado, só sai por intervenção manual + reset explícito.
5. **Cobertura de testes ≥ 75%.** Inclui chaos tests: mata processo, simula latency burst, simula DD máximo.

## Padrões Obrigatórios

- **Sem estado mutável fora de atomicidades.** Use `multiprocessing.Manager` ou `asyncio.Lock`.
- **Persistência síncrona** dos eventos críticos antes de retornar `deny` ao Strategy.
- **Heartbeat externo:** segundo servidor pinga o Risk Engine; sem heartbeat por 60s → cancel-all via REST.
- **Idempotência:** chamar `trigger_halt()` N vezes deve ter o mesmo efeito de 1 vez.

## Anti-Padrões (NUNCA fazer)

- Decisões baseadas em float (use Decimal).
- Cache de decisão "permitida" sem TTL — estado de mercado muda em ms.
- `except Exception` engolindo erro — Risk Engine deve **falhar fechado** (deny por padrão).
- Logs por f-string com dados sensíveis (PnL, posições).

## Testes Obrigatórios

Para cada gatilho de risco, ter:

1. **Teste happy path:** condição não violada → `allow`.
2. **Teste boundary:** exatamente no limite → comportamento definido (geralmente `allow` no `≤`, `deny` no `>`).
3. **Teste violação:** condição violada → `deny` + `RiskEvent` registrado.
4. **Teste persistência:** evento crítico chega ao banco antes do ACK.
5. **Property-based** com `hypothesis` para edge cases numéricos.

## Failure Modes Conhecidos

| Failure | Resposta esperada |
| --- | --- |
| Strategy envia ordem antes do book chegar | `deny` (sem mid_price = sem cálculo de risco) |
| Latency burst > limite | Pausa novas ordens, mantém existentes (não cancela) |
| Drawdown diário ultrapassado | `flatten` + halt 24h, alerta CRITICAL |
| Heartbeat externo perdido | `cancel_all()` via REST de emergência |
| Banco offline | Não permite novas ordens (não pode persistir evento) |
| Bug interno no Risk | Falha fechado: deny + alerta CRITICAL |
