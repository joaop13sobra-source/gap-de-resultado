#!/usr/bin/env python3
"""Monta o dados.json do Gap de Resultado a partir das exportações do MCP do Cockpit/Flow.

Entradas (arquivos JSON salvos pelas tools do MCP `cockpit`):
  --tabela     resultado de cockpit_query_table (formato {"data":[...]}, com healthScoreTable)
  --historico  resultado(s) de cockpit_query_history semanal com as 5 dimensões (pode repetir a flag)

Uso:
  python3 preparar_dados.py --tabela tabela.json --historico hist.json \
      --corte 2026-10-18 --coordenador nome.sobrenome --nome-coordenador "Nome Sobrenome" \
      --revisor "Nome do revisor" --saida dados.json

O resultado traz números, cores, candidato a gargalo e textos-rascunho. Antes do build, o agente
revisa `gargalo` e `texto` de cada projeto e preenche `plano` quando houver.
"""
import argparse, calendar, datetime as dt, json, os, re, unicodedata

DIM_COLS = [('Resultado', 'algorithm_results_score'), ('Operação de tráfego', 'algorithm_ops_paid_media_bool'),
            ('Qualidade', 'algorithm_delivery_bool'), ('Prazo', 'algorithm_deadlinae_bool'),
            ('Relacionamento', 'algorithm_service_quality_bool')]
FAMILIAS = {
    'topo': ('Geração de lead', 'Entra pouco lead ou lead caro'),
    'qualif': ('Lead → MQL', 'Lead não vira MQL'),
    'sql': ('MQL → SQL', 'MQL não vira SQL'),
    'fecha': ('SQL → Venda', 'SQL não vira venda'),
    'verba': ('Verba e ROAS', 'Investimento e retorno abaixo'),
}
ETAPAS = [  # chave, rótulo, coluna da meta, coluna do realizado, dinheiro?
    ('inv', 'Investimento', None, None, True),
    ('leads', 'Leads', 'paid_traffic_leads_milestone_qty', 'paid_traffic_leads_realized_qty', False),
    ('mql', 'MQL', 'paid_traffic_mql_milestone_qty', 'paid_traffic_mql_realized_qty', False),
    ('sql', 'SQL', 'paid_traffic_sql_milestone_qty', 'paid_traffic_sql_realized_qty', False),
    ('vendas', 'Vendas', 'paid_traffic_sales_milestone_qty', 'paid_traffic_sales_realized_qty', False),
    ('fat', 'Faturamento', 'paid_traffic_revenue_milestone_qty', 'paid_traffic_revenue_realized_qty', True),
]
INV_META = ['campaigns_budget_milestone_meta_qty', 'campaigns_budget_milestone_google_qty', 'campaigns_budget_milestone_linkedin_qty']
INV_REAL = ['campaigns_budget_current_meta_qty', 'campaigns_budget_current_google_qty', 'campaigns_budget_current_linkedin_qty']
GARGALO_FAMILIA = {'leads': 'topo', 'mql': 'qualif', 'sql': 'sql', 'vendas': 'fecha', 'fat': 'verba', 'inv': 'verba'}


def cel(h, col):
    c = h.get(col)
    if isinstance(c, dict):
        return c.get('value'), c.get('createdAt')
    return c, None


def num(v):
    if v is None or v == '':
        return None
    try:
        return float(str(v).replace(',', '.'))
    except ValueError:
        return None


def boolv(v):
    if isinstance(v, bool):
        return v
    if v in ('true', 'True', '1', 1):
        return True
    if v in ('false', 'False', '0', 0):
        return False
    return None


def nome_curto(n):
    n = re.split(r'\s+-\s+|\(', n)[0]
    n = re.sub(r'\b(LTDA|LTDA\.|S\.?A\.?|EIRELI|ME|EPP|COMERCIO|COM|DE|DA|DO|E)\b\.?', ' ', n, flags=re.I)
    n = re.sub(r'\s+', ' ', n).strip(' .,-')
    if n.isupper():
        n = ' '.join(w.capitalize() if len(w) > 3 else w for w in n.split())
    return n


def sigla(n, usadas):
    base = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode().upper()
    base = re.sub(r'[^A-Z0-9]', '', base)[:4] or 'PROJ'
    s, i = base, 1
    while s in usadas:
        i += 1
        s = f'{base}{i}'
    usadas.add(s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tabela', required=True)
    ap.add_argument('--historico', action='append', default=[])
    ap.add_argument('--corte', help='último dia com dado (AAAA-MM-DD)')
    ap.add_argument('--coordenador', help='username do Cockpit (project_coordinator), ex. nome.sobrenome')
    ap.add_argument('--nome-coordenador')
    ap.add_argument('--revisor', default='')
    ap.add_argument('--categoria', default='Executar')
    ap.add_argument('--semana', type=int)
    ap.add_argument('--apelidos', help='JSON extra {"nome no Cockpit": "nome curto"}; assets/apelidos.json é carregado sempre')
    ap.add_argument('--saida')
    ap.add_argument('--so-ids', action='store_true', help='só imprime os documentIds da carteira (para o cockpit_query_history)')
    a = ap.parse_args()
    if a.so_ids:
        rows = json.load(open(a.tabela))['data']
        rows = [r for r in rows if (not a.coordenador or r.get('project_coordinator') == a.coordenador)
                and (a.categoria == 'all' or r.get('category') == a.categoria)]
        print(json.dumps([r['documentId'] for r in rows]))
        return
    if not (a.corte and a.nome_coordenador and a.saida):
        ap.error('--corte, --nome-coordenador e --saida são obrigatórios')

    corte = dt.date.fromisoformat(a.corte)
    dias_mes = calendar.monthrange(corte.year, corte.month)[1]
    frac = corte.day / dias_mes
    inicio_mes = corte.replace(day=1).isoformat()
    semana = a.semana or corte.isocalendar()[1]
    seg = corte - dt.timedelta(days=corte.weekday())
    padrao = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'apelidos.json')
    apelidos = json.load(open(padrao)) if os.path.exists(padrao) else {}
    if a.apelidos:
        apelidos.update(json.load(open(a.apelidos)))

    rows = json.load(open(a.tabela))['data']
    if a.coordenador:
        rows = [r for r in rows if (r.get('project_coordinator') or '') == a.coordenador]
    if a.categoria != 'all':
        rows = [r for r in rows if r.get('category') == a.categoria]

    hist = {}
    for f in a.historico:
        for r in json.load(open(f))['data']:
            if r['referenceDate'] <= a.corte:
                hist.setdefault(r['projectDocumentId'], {})[r['referenceDate']] = r['values']
    semanas = sorted({d for h in hist.values() for d in h})[-8:]

    usadas, projetos, fora = set(), [], []
    for r in sorted(rows, key=lambda x: x['name']):
        h = r.get('healthScoreTable') or {}
        nome = apelidos.get(r['name']) or nome_curto(r['name'])
        hs = num(cel(h, 'algorithm_health_avg_score')[0])
        res = num(cel(h, 'algorithm_results_score')[0])
        if hs is None and res is None:
            continue
        grupo = 'hs' if hs is not None and hs < 21 else 'res' if res is not None and res < 7 else None
        if not grupo:
            fora.append({'nome': nome, 'hs': hs, 'resultado': res})
            continue
        pend = []
        etapas = []
        for k, rot, cm, cr, money in ETAPAS:
            if k == 'inv':
                ms = [num(cel(h, c)[0]) for c in INV_META]
                rs = [(num(cel(h, c)[0]), cel(h, c)[1]) for c in INV_REAL]
                meta = sum(x for x in ms if x) or None
                vals = [x for x, _ in rs if x is not None]
                real = sum(vals) if vals else None
                ts = max([t for x, t in rs if x is not None and t] or [''])
            else:
                meta = num(cel(h, cm)[0])
                real, ts = cel(h, cr)
                real = num(real)
            if not meta:
                continue
            stale = bool(ts) and ts[:10] < inicio_mes
            if stale:
                pend.append(f'{rot} sem lançamento do mês (último registro {ts[8:10]}/{ts[5:7]})')
                real = None
            esp = meta * frac
            pct = (real / esp) if (real is not None and esp) else None
            etapas.append({'k': k, 'rotulo': rot, 'dinheiro': money, 'meta': meta, 'esperado': esp,
                           'real': real, 'pct': pct})
        E = {e['k']: e for e in etapas}

        # candidato a gargalo: menor pct relativo à etapa anterior no funil comercial
        cand, ant = [], None
        for k in ('leads', 'mql', 'sql', 'vendas'):
            e = E.get(k)
            if not e or e['pct'] is None:
                continue
            score = e['pct'] if ant is None else (e['pct'] / ant if ant else e['pct'])
            cand.append((score, k))
            ant = e['pct'] if e['pct'] else ant
        if cand:
            etapa = min(cand)[1]
        else:
            etapa = 'fat' if 'fat' in E else 'inv'
        fam = GARGALO_FAMILIA[etapa]

        conv = []
        def taxa(a_, b_, rot):
            ea, eb = E.get(a_), E.get(b_)
            if not ea or not eb:
                return
            plano = eb['meta'] / ea['meta'] if ea['meta'] else None
            real = (eb['real'] / ea['real']) if (ea['real'] and eb['real'] is not None) else None
            conv.append({'rotulo': rot, 'plano': plano, 'real': real, 'tipo': 'pct'})
        taxa('leads', 'mql', 'Leads → MQL'); taxa('mql', 'sql', 'MQL → SQL'); taxa('sql', 'vendas', 'SQL → Venda')
        if 'mql' not in E:
            taxa('leads', 'vendas', 'Leads → Venda')
        if E.get('inv') and E.get('leads'):
            i, l = E['inv'], E['leads']
            conv.append({'rotulo': 'Custo por lead', 'plano': i['meta'] / l['meta'] if l['meta'] else None,
                         'real': (i['real'] / l['real']) if (i['real'] and l['real']) else None, 'tipo': 'brl', 'menor_melhor': True})
        if E.get('inv') and E.get('fat') and not E.get('leads'):
            i, f = E['inv'], E['fat']
            conv.append({'rotulo': 'ROAS', 'plano': f['meta'] / i['meta'] if i['meta'] else None,
                         'real': (f['real'] / i['real']) if (i['real'] and f['real'] is not None) else None, 'tipo': 'x'})

        ops_ok = boolv(cel(h, 'algorithm_ops_paid_media_bool')[0])
        ops_motivo = cel(h, 'paid_traffic_ops_false_reason')[0] or ''
        if ops_ok is False:
            pend.append(f'Ops Tráfego FALSE: {ops_motivo or "sem motivo lançado"}')

        tipo_meta = cel(h, 'results_goal_aligned_with_client')[0]
        meta_q = num(cel(h, 'results_goal_qty')[0])
        meta_r = num(cel(h, 'results_goal_reached_qty')[0])
        meta_oficial = None
        if tipo_meta and meta_q:
            meta_oficial = {'tipo': tipo_meta, 'meta': meta_q, 'alcancado': meta_r,
                            'pct': (meta_r / (meta_q * frac)) if meta_r is not None else None}
            if tipo_meta == 'Faturamento' and E.get('fat') and abs(E['fat']['meta'] - meta_q) > 1:
                pend.append(f'Meta de tráfego R$ {E["fat"]["meta"]:,.0f} × meta oficial R$ {meta_q:,.0f}'.replace(',', '.'))

        anomalia = cel(h, 'deliveries_project_anomaly')[0] or ''
        anomalia_motivo = cel(h, 'deliveries_project_anomaly_reason')[0] or ''
        dims = []
        for rot, col in DIM_COLS:
            v = cel(h, col)[0]
            ok = (num(v) is not None and num(v) >= 7) if col == 'algorithm_results_score' else boolv(v)
            if ok:
                texto = ''
            elif col == 'algorithm_results_score':
                texto = f'Resultado {int(res) if res is not None else "—"}, abaixo de 7.'
            elif col == 'algorithm_deadlinae_bool':
                texto = '. '.join(x for x in [anomalia if anomalia != 'Sem anomalia' else '', anomalia_motivo] if x) or 'Prazo falso no Cockpit, sem anomalia preenchida.'
            elif col == 'algorithm_ops_paid_media_bool':
                texto = ops_motivo or 'Operação de tráfego falsa, sem motivo lançado.'
            else:
                texto = f'{rot} falso no Cockpit, sem motivo de anomalia preenchido.'
            dims.append({'rotulo': rot, 'ok': ok, 'texto': texto})
        hp = hist.get(r['documentId'], {})
        historico = {}
        for rot, col in DIM_COLS:
            linha = []
            for d in semanas:
                v = (hp.get(d) or {}).get(col)
                linha.append(None if v is None else ((num(v) or 0) >= 7 if col == 'algorithm_results_score' else boolv(v)))
            if linha and linha[-1] is None:
                # semana mais recente sem histórico: usa a situação atual da tabela
                linha[-1] = next(x['ok'] for x in dims if x['rotulo'] == rot)
            historico[rot] = linha

        e_g = E.get(etapa)
        if e_g and e_g['pct'] is not None:
            rascunho = f'{e_g["rotulo"]} é onde o funil quebra: {e_g["pct"]*100:.0f}% do esperado até {corte:%d/%m}.'
        else:
            rascunho = 'Revisar: sem etapa comercial com meta e realizado lançados.'
        projetos.append({
            'id': sigla(nome, usadas), 'documentId': r['documentId'], 'nome': nome, 'nome_cockpit': r['name'],
            'grupo': grupo, 'hs': hs, 'resultado': res, 'meta_oficial': meta_oficial,
            'gargalo': {'familia': fam, 'etapa': etapa, 'secundario': ''}, 'texto': rascunho,
            'etapas': etapas, 'conversoes': conv, 'pendencias': pend,
            'dimensoes': dims, 'historico': historico, 'plano': [], 'plano_nota': '',
        })

    ordem = {'hs': 0, 'res': 1}
    projetos.sort(key=lambda p: (ordem[p['grupo']], p['hs'] if p['grupo'] == 'hs' else (p['resultado'] or 0)))
    dados = {
        'semana': semana, 'ano': corte.year, 'inicio_semana': seg.isoformat(), 'corte': a.corte,
        'dias_mes': dias_mes, 'coordenador': a.nome_coordenador, 'revisor': a.revisor,
        'semanas_historico': semanas, 'familias': FAMILIAS, 'projetos': projetos, 'fora': fora,
        'fonte': f'Cockpit, aba Gestão de Tráfego (lançamentos até {corte:%d/%m}).',
    }
    json.dump(dados, open(a.saida, 'w'), ensure_ascii=False, indent=1)
    print(f'{len(projetos)} projetos no recorte, {len(fora)} fora; histórico com {len(semanas)} semanas -> {a.saida}')


if __name__ == '__main__':
    main()
