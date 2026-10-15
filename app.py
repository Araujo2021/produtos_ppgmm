import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter

from config_docentes import DOCENTES
from db import init_db, load_works, stats, clear_db, get_mappings, save_mapping
from updater import update_all, MIN_YEAR
from graph import make_graph_figure

st.set_page_config(
    page_title="Publicações dos Docentes do Doutorado Multicêntrico em Matemática de Minas Gerais",
    page_icon="🎓",
    layout="wide",
)

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 3rem;}
.hero {
  padding: 1.25rem 1.5rem;
  border: 1px solid rgba(120,120,120,.25);
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(35,90,130,.10), rgba(90,35,130,.06));
  margin-bottom: 1rem;
}
.hero h1 {margin:0; font-size:2rem;}
.hero p {margin:.35rem 0 0 0; opacity:.75;}
.pub-card {
  border: 1px solid rgba(120,120,120,.24);
  border-radius: 14px;
  padding: 1rem 1.1rem;
  margin:.65rem 0;
}
.small {opacity:.72; font-size:.91rem;}
</style>
""", unsafe_allow_html=True)

init_db()

st.markdown("""
<div class="hero">
<h1>Publicações dos Docentes do Doutorado Multicêntrico em Matemática de Minas Gerais</h1>
<p>Catálogo consolidado, deduplicado e com rede de colaboração.</p>
</div>
""", unsafe_allow_html=True)

is_admin = st.session_state.get("is_admin", False)

with st.sidebar:
    st.header("Filtro de Exibição")
    selected_min_year = st.number_input("Mostrar publicações a partir do ano:", min_value=1950, max_value=2030, value=MIN_YEAR)
    
    works = load_works(selected_min_year)

    _, last = stats()
    st.metric("Total de publicações", len(works))
    st.caption(f"Última atualização: {last or 'ainda não realizada'}")
    
    if is_admin:
        st.divider()
        st.subheader("⚙️ Painel de Administração")
        st.caption("Modo de administrador ativado.")

        st.caption("Importação do scriptLattes (Recomendado)")
        uploaded_jsons = st.file_uploader("Selecione os arquivos JSON gerados pelo scriptLattes", type=["json"], accept_multiple_files=True)
        if uploaded_jsons:
            if st.button("📥 Processar arquivos JSON", use_container_width=True):
                from importer_scriptlattes import parse_scriptlattes_json
                total_json = 0
                errs_json = []
                with st.spinner("Lendo arquivos JSON..."):
                    for ufile in uploaded_jsons:
                        t, err = parse_scriptlattes_json(ufile.getvalue().decode("utf-8", errors="ignore"))
                        total_json += t
                        errs_json.extend(err)
                st.success(f"{total_json} artigos importados dos arquivos do scriptLattes!")
                if errs_json:
                    with st.expander(f"Avisos ({len(errs_json)})"):
                        for e in errs_json: st.write("•", e)
                st.rerun()

        st.markdown("---")
        st.caption("A versão 1 usa OpenAlex como fonte automática principal e mantém os links oficiais do Currículo Lattes.")
        if st.button("🔄 Atualizar publicações", use_container_width=True, type="primary"):
            bar = st.progress(0, text="Iniciando...")
            def prog(p, text):
                bar.progress(min(1.0, max(0.0, p)), text=text)
            with st.spinner("Consultando bases bibliográficas..."):
                result = update_all(prog)
            bar.empty()
            st.success(f"Atualização concluída: {result['registros_processados']} registros processados.")
            if result["erros"]:
                with st.expander(f"Avisos ({len(result['erros'])})"):
                    for e in result["erros"]:
                        st.write("•", e)
            st.rerun()

        st.markdown("---")
        if st.button("🗑️ Limpar banco de dados", use_container_width=True):
            clear_db()
            st.success("Banco de dados apagado com sucesso. Atualize a página.")
            st.rerun()

        st.markdown("---")
        if st.button("🚪 Sair do modo admin", use_container_width=True):
            st.session_state["is_admin"] = False
            st.rerun()
    else:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.expander("🔒 Área de Administração", expanded=False):
            admin_pwd = st.text_input("Senha", type="password", key="admin_pwd_input")
            if st.button("Entrar", key="btn_admin_login"):
                if admin_pwd == "ppgmm2025@":
                    st.session_state["is_admin"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")

def render_pub(w):
    if w.get("doi"):
        doi_str = w['doi']
        doi_url = doi_str if doi_str.startswith("http") else f"https://doi.org/{doi_str}"
        doi_html = f'DOI: <a href="{doi_url}" target="_blank" style="text-decoration:none; color:#0366d6;">{doi_str}</a>'
    elif w.get("url"):
        doi_html = f'<a href="{w["url"]}" target="_blank" style="text-decoration:none; color:#0366d6;">Link da publicação</a>'
    else:
        doi_html = "Sem DOI/Link identificado"
        
    journal = w.get("journal") or "Periódico/fonte não informado"
    authors = ", ".join(w["authors"])
    docentes_txt = ", ".join(x.title() for x in w["docentes"])
    
    st.markdown(f"""
<div class="pub-card">
<b>{w['title']}</b><br>
<span class="small">{authors}</span><br>
{journal} • <b>{w['year']}</b> • {doi_html}<br>
<span class="small">Docente(s) do programa: {docentes_txt} • Citações OpenAlex: {w.get('cited_by',0)}</span>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["📚 Publicações", "📅 Por ano", "👤 Por docente", "📈 Indicadores", "🕸️ Colaborações", "🧑‍🏫 Docentes"])

# ---------- Publicações ----------
with tabs[0]:
    st.subheader("Catálogo de publicações")
    if not works:
        st.info("O banco está vazio. Clique em **Atualizar publicações** na barra lateral para realizar a primeira coleta.")
    else:
        years = sorted({w["year"] for w in works}, reverse=True)
        docentes = [d["nome"] for d in DOCENTES]
        c1,c2,c3 = st.columns([2,1,1])
        q = c1.text_input("Buscar por título, periódico ou autor")
        year = c2.selectbox("Ano", ["Todos"]+years)
        docente = c3.selectbox("Docente", ["Todos"]+docentes)

        filtered = works
        if year != "Todos":
            filtered = [w for w in filtered if w["year"] == int(year)]
        if docente != "Todos":
            filtered = [w for w in filtered if docente in w["docentes"]]
        if q:
            qq = q.lower()
            filtered = [w for w in filtered if qq in (
                w["title"]+" "+(w.get("journal") or "")+" "+" ".join(w["authors"])
            ).lower()]

        st.caption(f"{len(filtered)} publicação(ões) encontrada(s).")
        
        current_year = None
        for w in filtered:
            if w["year"] != current_year:
                current_year = w["year"]
                st.markdown(f"#### 📅 {current_year}")
            render_pub(w)

# ---------- Por ano ----------
with tabs[1]:
    st.subheader("Produção organizada por ano")
    if works:
        for y in sorted({w["year"] for w in works}, reverse=True):
            subset = [w for w in works if w["year"] == y]
            with st.expander(f"{y} — {len(subset)} publicação(ões)", expanded=(y==max(w["year"] for w in works))):
                for w in subset:
                    render_pub(w)
    else:
        st.info("Atualize o banco para visualizar os anos.")

# ---------- Por docente ----------
with tabs[2]:
    st.subheader("Produção por docente")
    selected = st.selectbox("Selecione o docente", [d["nome"] for d in DOCENTES], key="docente_page")
    meta = next(d for d in DOCENTES if d["nome"] == selected)
    st.link_button("Abrir Currículo Lattes", meta["lattes"])
    own = [w for w in works if selected in w["docentes"]]
    c1,c2,c3 = st.columns(3)
    c1.metric("Publicações", len(own))
    c2.metric("Citações (soma OpenAlex)", sum(w.get("cited_by",0) for w in own))
    c3.metric("Colaborações internas", sum(1 for w in own if len(w["docentes"]) > 1))
    for y in sorted({w["year"] for w in own}, reverse=True):
        st.markdown(f"### {y}")
        for w in [x for x in own if x["year"] == y]:
            render_pub(w)

# ---------- Indicadores ----------
with tabs[3]:
    st.subheader("Indicadores")
    if works:
        by_year = pd.DataFrame(
            [{"Ano": y, "Publicações": sum(1 for w in works if w["year"]==y)} for y in sorted({w["year"] for w in works})]
        )
        st.plotly_chart(px.bar(by_year, x="Ano", y="Publicações", title="Publicações por ano"), use_container_width=True)

        counts = []
        for d in DOCENTES:
            counts.append({"Docente": d["nome"].title(), "Publicações": sum(d["nome"] in w["docentes"] for w in works)})
        dfc = pd.DataFrame(counts).sort_values("Publicações", ascending=True)
        fig_prod = px.bar(
            dfc, 
            x="Publicações", 
            y="Docente", 
            orientation="h", 
            title="Produção por docente",
            height=850,
            text="Publicações"
        )
        fig_prod.update_traces(textposition='outside')
        st.plotly_chart(fig_prod, use_container_width=True)

        journals = Counter(w.get("journal") or "Não informado" for w in works)
        jdf = pd.DataFrame(journals.most_common(15), columns=["Periódico","Publicações"]).sort_values("Publicações", ascending=True)
        fig_jour = px.bar(
            jdf, 
            x="Publicações", 
            y="Periódico", 
            orientation="h", 
            title="15 periódicos/fontes mais frequentes",
            height=600,
            text="Publicações"
        )
        fig_jour.update_traces(textposition='outside')
        st.plotly_chart(fig_jour, use_container_width=True)
    else:
        st.info("Atualize o banco para gerar os gráficos.")

# ---------- Colaborações ----------
with tabs[4]:
    st.subheader("Grafo interativo de colaboração entre docentes")
    st.caption("Cada vértice representa um docente. O número exibido sobre a aresta é a quantidade de publicações em coautoria no período selecionado.")
    fig, edges = make_graph_figure(works)
    if edges:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
        table = pd.DataFrame(
            [{"Docente A": a.title(), "Docente B": b.title(), "Artigos em colaboração": n}
             for (a,b), n in sorted(edges.items(), key=lambda kv: kv[1], reverse=True)]
        )
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma colaboração interna identificada ainda. Execute a atualização.")

# ---------- Docentes ----------
with tabs[5]:
    st.subheader("Docentes cadastrados")
    cols = st.columns(3)
    for i,d in enumerate(DOCENTES):
        with cols[i % 3]:
            st.markdown(f"**{d['nome'].title()}**")
            st.link_button("Lattes", d["lattes"], use_container_width=True)



st.divider()
st.caption("Versão 1.3 • scriptLattes • banco SQLite")
