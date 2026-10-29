---
name: gap-de-resultado
description: Monta o "Gap de Resultado" semanal (Quality Check de carteira) de um coordenador a partir do MCP do Flow/Cockpit e publica no Vercel. Para cada projeto com HS abaixo de 21 ou Resultado abaixo de 7, mostra o funil realizado × esperado até a data de corte (Gestão de Tráfego do Cockpit), o gargalo, as conversões plano × realizado, as pendências de dado, as 5 dimensões do Health Score com a grade das últimas 8 semanas e o plano de ação 5W1H. Gera a página por script (dados.json → HTML no visual da S42, logo V4, tema claro). Use quando pedirem "gap de resultado", "quality check da carteira", "onde o funil quebra na carteira da <pessoa>", "monta a S<nº>", "atualiza o gap da semana" ou para lançar planos de ação nos projetos de um gap já publicado.
---

# Gap de Resultado (Quality Check semanal da carteira)

Uma página HTML por semana e por coordenador, publicada no Vercel. Responde: **em quais projetos da carteira o
funil está quebrando, em que etapa, e o que vamos fazer**. Modelo aprovado: Gap de Resultado S42.

Fluxo: MCP do Cockpit (tabela + histórico) → `scripts/preparar_dados.py` → revisão do agente no `dados.json`
(gargalo, texto, planos) → `scripts/build_gap.py` → print de conferência → `vercel deploy`.

---

## 1. Confirmar os parâmetros (perguntar só o que não estiver claro)

| Parâmetro | Exemplo | Observação |
|---|---|---|
| Coordenador (username do Cockpit) e nome | `nome.sobrenome`, "Nome Sobrenome" | `project_coordinator` na tabela. Lista: `cockpit_list_coordinators` |
| Revisor (quem recebe) | "Nome do revisor" | aparece no topo: "Quality Check · Coordenador → Revisor" |
| Data de corte | último sábado/domingo com lançamento | define o esperado = meta do mês × dia/dias do mês |
| Semana | ISO da data de corte (padrão do script) | só passar `--semana` se o usuário pedir outro número |
| Projetos fora do Cockpit | projeto acompanhado só em planilha | entram à mão (ver 4.4) |

## 2. Buscar os dados no MCP do Flow/Cockpit (server `cockpit`)

1. **Tabela atual** — `cockpit_query_table` com `filterByCategory: "Executar"`, `fetchAllPages: true`, `sortBy: "name"`,
   `pageSize: 250` e o recorte da carteira (`filterByUser` com o documentId do coordenador, ou `filterBySquad`).
   O resultado é grande e o harness salva em arquivo (`tool-results/mcp-cockpit-cockpit_query_table-*.txt`): use esse caminho.
2. **IDs da carteira** — `python3 scripts/preparar_dados.py --tabela <arquivo> --coordenador <username> --so-ids`.
3. **Histórico das dimensões** — `cockpit_query_history` com:
   `granularity: "weekly"`, `startDate` = corte − 56 dias, `endDate` = corte, `timezone: "America/Sao_Paulo"`,
   `filterByCategory: "all"`, `filterByStatus: "all"`, `pageSize: 500`, `parseTypes: true`,
   `projectDocumentIds`: a lista do passo 2, `columns`: `["algorithm_results_score","algorithm_ops_paid_media_bool","algorithm_delivery_bool","algorithm_deadlinae_bool","algorithm_service_quality_bool"]`.
   - Se vier mais de uma página (`meta.pagination.pageCount` > 1), buscar todas e passar cada arquivo com `--historico`.
   - Se o resultado vier inline (pequeno), gravar o JSON com Write num arquivo do scratchpad e usar esse arquivo.
   - Se a semana mais recente faltar no histórico, o script usa a situação atual da tabela nessa coluna.

Colunas que o script lê da tabela (referência, não precisa pedir): `algorithm_health_avg_score`, `algorithm_results_score`,
`campaigns_budget_{milestone,current}_{meta,google,linkedin}_qty`, `paid_traffic_{leads,mql,sql,sales,revenue}_{milestone,realized}_qty`,
`results_goal_aligned_with_client`, `results_goal_qty`, `results_goal_reached_qty`, os 5 `algorithm_*_bool`,
`deliveries_project_anomaly(_reason)`, `paid_traffic_ops_false_reason`.

## 3. Gerar o rascunho

```bash
python3 scripts/preparar_dados.py --tabela <tabela> --historico <hist1> [--historico <hist2>] \
  --corte AAAA-MM-DD --coordenador <username> --nome-coordenador "Nome" --revisor "Nome" \
  --saida "<pasta do deploy>/dados.json"
```

O script já resolve:
- **Recorte**: HS < 21 → grupo `hs`; senão Resultado < 7 → grupo `res`; o resto vai para "Fora do recorte".
- **Funil**: só etapas com meta no mês. Esperado = meta × dia/dias do mês. Cor: ≥100% verde, 70–99% amarelo, <70% vermelho.
- **Lançamento velho**: realizado lançado antes do dia 1º do mês vira "a lançar" + pendência "último registro dd/mm".
- **Conversões**: taxas do plano (razão entre metas) × realizado; custo por lead; ROAS em e-commerce sem lead.
- **Pendências automáticas**: lançamento velho, Ops Tráfego FALSE com motivo, meta de tráfego ≠ meta oficial.
- **Dimensões**: ✅ quando certa; falsa traz o motivo (Prazo = anomalia + motivo; Operação de tráfego = motivo do FALSE).
- **Grade das últimas 8 semanas** por dimensão (✓/✗, contagem "x/8"). Resultado conta ✓ com nota ≥ 7.
- **Nomes curtos** pelo `assets/apelidos.json` (nome do Cockpit → nome da página), que fica só na máquina (fora do git).
  Primeira vez: copiar `assets/apelidos.exemplo.json` para `assets/apelidos.json`. Projeto novo com nome longo: acrescentar lá.

## 4. Revisar o `dados.json` (trabalho do agente, sempre)

### 4.1 Gargalo de cada projeto
O script sugere `gargalo.etapa` pela maior queda relativa entre etapas (leads → mql → sql → vendas). É só candidato:
conferir com o funil e ajustar `gargalo.familia` (`topo`, `qualif`, `sql`, `fecha`, `verba`), `gargalo.etapa`
(`inv`, `leads`, `mql`, `sql`, `vendas`, `fat` — marca a linha "gargalo") e, se fizer sentido, `gargalo.secundario`
(ex.: "+ Lead → MQL"). Verba bem abaixo do ritmo travando o volume → família `verba`, etapa `inv`.
E-commerce (sem lead, só faturamento/ROAS) → `verba`.

### 4.2 Texto do gargalo (`texto`)
Substituir o rascunho por 2–4 frases com números, no tom da S42: onde quebra, quanto do esperado, o que puxa
(verba, custo por lead, conversão), e o que o plano pressupõe. Ex.: "Entram poucos leads e eles saem caros: 98 contra
251 esperados (39%), com custo por lead de R$ 16,92, quase o dobro dos R$ 9,26 do plano." Contexto que o usuário
contar entra no fim como "Contexto do time: …". Sem jargão interno de ferramenta.

### 4.3 Planos de ação (quando o usuário ditar)
Cada projeto tem `plano` (lista) e `plano_nota` (ex.: "Plano informado pela coordenação em 23/10/2026."):
```json
{"titulo": "Retomar o Google Ads", "porque": "...", "onde": "Google Ads", "quando": "23/10/2026", "quem": "V4", "como": "..."}
```
Regras: campo não informado = `"a definir"` (aparece em destaque). Não inventar responsável, prazo ou motivo; quando
deduzir algo, avisar o usuário. Projeto sem nome no áudio: identificar pelo contexto (números da meta, pessoas citadas
em `estrutura-comercial.md` do cliente) e confirmar no retorno. Falas duras ("atendimento péssimo") viram descrição
do que falta (sem follow-up, sem condução), porque a página circula na coordenação.

### 4.4 Projeto fora do Cockpit
Acrescentar à mão em `projetos` com `"sem_cockpit": true`, `grupo`, `gargalo`, `texto`, `pills_extra` (ex.:
`["Leads no mês: 58 gerados · 39 no Flow"]`), `sobrancelha` (ex.: "Carteira de outro coordenador") e `etapas: []`.
A página mostra "Projeto fora do Cockpit: sem dimensões nem histórico".

## 5. Gerar, conferir e publicar

```bash
python3 scripts/build_gap.py "<pasta>/dados.json" "<pasta>/index.html"
```
- **Pasta**: `~/Desktop/Projetos V4/growth/gap-de-resultado-s<NN>-deploy/` (uma por semana; a mesma pasta mantém o link).
- **Print antes de publicar** (puppeteer local, ver memória de screenshot): topo da página e 1–2 cards, em 1280 px e 390 px.
  `NODE_PATH=<pasta com node_modules/puppeteer> node scripts/shot.js <url-ou-file://> <saida.png> <largura> [pv-ID]`
  (instalar uma vez no scratchpad: `npm init -y && npm i puppeteer`).
- **Deploy**: `vercel deploy --prod --yes --name gap-de-resultado-s<NN>` dentro da pasta (com `.gitignore` contendo `.vercel`).
- **Link real**: rodar `vercel inspect <deployment>` e usar o alias listado. Nunca anunciar `<nome>.vercel.app` sem
  conferir: o domínio curto pode pertencer a outra conta (já aconteceu: o link certo tinha um sufixo extra).
- Conferir no ar com `curl` (título e um trecho novo) antes de responder.

## 6. Atualizações na mesma semana
Editar o `dados.json` da pasta (gargalo, texto, plano) e rodar o build de novo; publicar na mesma pasta. A contagem
"N de M com plano de ação 5W1H", as famílias do topo e o mapa do funil se recalculam sozinhos.

## Arquivos
- `scripts/preparar_dados.py` — tabela + histórico do Cockpit → `dados.json`
- `scripts/build_gap.py` — `dados.json` → `index.html`
- `scripts/shot.js` — print de conferência
- `assets/style.css`, `assets/logo-v4.png` — visual da S42 (tokens claro/escuro, página fixa no tema claro)
- `assets/apelidos.exemplo.json` — modelo do `apelidos.json` local (nomes curtos dos projetos; não vai para o repo)
- `assets/exemplo/dados-exemplo.json` — saída do script anonimizada (corte 25/10/2026, sem planos)
