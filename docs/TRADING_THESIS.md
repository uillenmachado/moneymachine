# Tese de Trading — Máquina de Dinheiro

> Documento canônico. Qualquer mudança de estratégia, premissas ou metas deve
> ser registrada aqui via PR com justificativa. Versão atual: **0.0.1**.

---

## 1. Resumo Executivo

**Estratégia:** Grid Adaptativo com camada de Market Making (Avellaneda-Stoikov + skew por Order Flow Imbalance), operando majoritariamente com ordens Maker em pares de altíssima liquidez (BTC/USDT, ETH/USDT inicialmente).

**Tese central:** explorar a microestrutura de mercado — spread bid/ask, mean reversion intradiário e provimento de liquidez — sem prever direção. Lucro vem da soma estatística de muitas operações pequenas, não de calls direcionais.

**Meta de performance (anualizada, NÃO mensal):**

- Sharpe Ratio ≥ 1.5
- Retorno líquido 12-25% a.a. (≈ 1-2%/mês em média, **com variância mensal**)
- Max Drawdown ≤ 8%
- Calmar Ratio ≥ 2.0

> ⚠️ Espere meses de -2% a -3% intercalados com meses de +3% a +5%. O alvo é a
> **média anualizada**, não um piso mensal. Comunicar isto corretamente é
> parte da saúde mental do projeto.

---

## 2. Por que Grid + MM (e não outras estratégias)

| Estratégia | Veredito | Motivo |
| --- | --- | --- |
| **Grid Adaptativo** | ✅ Adotada (base) | Robusta para retail, lucra em ranging (60-70% do tempo em cripto), simples de auditar |
| **Market Making puro** | ⚠️ Camada complementar | Exige modelagem séria de adverse selection; sozinho compete com HFT |
| **Trend following** | ❌ Excluída | Fora da tese (sistema não prevê direção) |
| **Cross-exchange arb** | ❌ Excluída (MVP) | Exige infra dupla, capital lockado em N exchanges |
| **DeFi LP (Uniswap v3)** | ❌ Excluída (MVP) | Impermanent loss, gas, risco de smart contract |
| **Alavancagem direcional** | ❌ Excluída | Risco de liquidação incompatível com a tese |

---

## 3. Modelo Matemático (alto nível)

### 3.1. Grid Adaptativo

- Largura do nível: `tick_size × max(round(k × ATR(14) / tick_size), N_min)`
- Número de níveis ativos por lado: função do capital alocado.
- Capital por nível: `total / (2 × n_levels)` (igual para ambos os lados).

### 3.2. Camada Market Making (Avellaneda-Stoikov)

$$ r(s, q, t) = s - q \cdot \gamma \cdot \sigma^2 \cdot (T - t) $$
$$ \delta^a + \delta^b = \gamma \cdot \sigma^2 \cdot (T - t) + \frac{2}{\gamma} \ln\!\left(1 + \frac{\gamma}{\kappa}\right) $$

Onde:

- $s$ = mid price
- $q$ = inventário (sinal indica direção)
- $\gamma$ = aversão a risco (parâmetro calibrado)
- $\sigma$ = volatilidade do ativo
- $\kappa$ = intensidade de arrivals (calibrado dos dados)

### 3.3. Skew por Order Flow Imbalance (OFI)

$$ \text{OFI}_t = \sum_{i=t-w}^{t} (\Delta V^{bid}_i - \Delta V^{ask}_i) $$

Quando OFI > limite → desloca quotes para cima (fluxo comprador detectado).
Quando OFI < -limite → desloca quotes para baixo (fluxo vendedor).

Objetivo: reduzir adverse selection. Implementa Cartea-Jaimungal (2017).

### 3.4. Detector de Regime (kill switch da estratégia)

- ADX(14) > 30 **OU** Hurst exponent > 0.55 → modo TENDÊNCIA detectado.
- Ação: pausa novas ordens, fecha inventário gradualmente, aguarda retorno a regime de mean reversion.

---

## 4. Premissas Validáveis no Backtest

| Premissa | Como será testada (Fase 3) |
| --- | --- |
| Spread médio diário ≥ 2× custo de Maker | Análise estatística de book L2 |
| Volatilidade horária permite re-cotação rentável | Distribuição de retornos em janelas de 1h |
| Adverse selection é controlável com skew OFI | A/B com e sem OFI em walk-forward |
| Detector de regime previne grandes drawdowns | Stress test em flash crashes históricos |

---

## 5. Riscos Reconhecidos e Mitigações

| Risco | Severidade | Mitigação |
| --- | --- | --- |
| Adverse selection (toxic flow) | 🔴 Alta | Skew OFI; quotes 1-3 ticks atrás do best bid/ask |
| Tendência forte unidirecional | 🔴 Alta | Detector ADX/Hurst + halt automático |
| Exchange quebra (FTX, Mt.Gox) | 🟡 Média | Saque mensal de 20% do lucro para cold wallet |
| Falha de WebSocket | 🟡 Média | Reconexão exponencial + watchdog |
| Falha do processo principal | 🔴 Alta | Risk Engine em processo isolado + kill switch externo em segundo servidor |
| Bug com posição aberta | 🔴 Alta | Reconciliação periódica + cobertura de testes ≥ 75% no Risk Engine |
| Depeg de stablecoin (UST 2022) | 🟡 Média | Diversificação USDT + USDC + monitor de peg |
| Latência aumenta sem aviso | 🟡 Média | Histograma p99 com circuit breaker em 500ms |
| Tributação não-paga (BR) | 🟡 Média | Export automatizado mensal para contador (IN 1888/2019) |
| Mudança regulatória CVM/RFB | 🟢 Baixa (curto prazo) | Monitorar; preparar migração de PF→PJ se necessário |

---

## 6. Critérios de Sucesso por Fase

| Fase | Critério Go/No-Go |
| --- | --- |
| 0 — Fundação | `docker compose up` sobe stack, lint+mypy+tests verdes |
| 1 — Benchmark | Matriz de decisão preenchida com dados reais de 72h |
| 2 — Quant | Notebooks reproduzíveis, parâmetros versionados em YAML |
| 3 — Backtest | **Sharpe ≥ 1.5, MaxDD ≤ 8% em 6+ janelas walk-forward** |
| 4 — Core | Cobertura ≥ 75% no Risk Engine, chaos test passa |
| 5 — Paper | **14d testnet, métricas ±15% do backtest, uptime ≥ 99.5%** |
| 6 — Micro-prod | **30d com Sharpe rolling 30d ≥ 1.2 antes de escalar** |

---

## 7. Plano de Escalonamento de Capital

| Marco | Condição | Capital Alvo | Pares |
| --- | --- | --- | --- |
| Micro-lote | Aprovação Fase 5 | USD 500-1.000 | BTC/USDT |
| Escala 1 | 30d com Sharpe rolling ≥ 1.2 | USD 2.000-5.000 | BTC/USDT + ETH/USDT |
| Escala 2 | 60d com Sharpe rolling ≥ 1.2 | USD 10.000-15.000 | + 1 par top-20 |
| Escala 3 | 120d com Sharpe rolling ≥ 1.2 | USD 25.000+ | Avaliar PJ + diversificação |

**Saque programado:** 20% do lucro mensal realizado vai para cold wallet (mitigação de risco de contraparte).

---

## 8. Decisões Pendentes (Bloqueios para Fase 1)

- [ ] Consulta a contador especializado em cripto BR (ação manual do usuário).
- [ ] Aquisição de tick data L2 — definir fornecedor (exchange nativa, Kaiko, CoinAPI). Custo estimado: USD 0-500/mês.
- [ ] Decisão de hospedagem: AWS vs Hetzner vs GCP (depende da região da exchange escolhida na Fase 1).

---

## 9. Referências

- Avellaneda, M. & Stoikov, S. (2008). *High-frequency trading in a limit order book.*
- Cartea, Á., Jaimungal, S. & Penalva, J. (2015). *Algorithmic and High-Frequency Trading.* Cambridge.
- Cartea, Á. & Jaimungal, S. (2017). *Algorithmic trading with model uncertainty.*
- Glosten, L. & Milgrom, P. (1985). *Bid, ask and transaction prices in a specialist market with heterogeneously informed traders.*
- Almgren, R. & Chriss, N. (2001). *Optimal execution of portfolio transactions.*
- Receita Federal — Instrução Normativa 1888/2019 (declaração de cripto).
