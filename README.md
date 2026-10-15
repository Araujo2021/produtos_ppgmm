# Produtos dos Docentes do Doutorado Multicêntrico de Minas Gerais

Primeira versão funcional de um painel Streamlit para catalogar, deduplicar e visualizar publicações científicas dos docentes do programa desde 2025.

## Recursos

- 33 docentes já cadastrados com seus links Lattes.
- Coleta automática inicial via OpenAlex.
- Banco local SQLite (`produtos.db`).
- Deduplicação por DOI e, na ausência de DOI, por título normalizado.
- Busca textual.
- Página por ano.
- Página por docente.
- Gráficos de produção.
- Rede interativa de colaboração entre docentes.
- Peso e rótulo de cada aresta = número de artigos em coautoria.
- Botão de atualização.

## Instalação no macOS

Abra o Terminal dentro da pasta do projeto e execute:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

O navegador abrirá automaticamente. Se não abrir, use o endereço indicado pelo Streamlit (normalmente `http://localhost:8501`).

## Primeira utilização

1. Abra o aplicativo.
2. Clique em **Atualizar publicações**.
3. Aguarde a identificação dos pesquisadores no OpenAlex e a coleta das publicações a partir de 2025.
4. Navegue pelas abas.

## Observação sobre Lattes, Google Scholar e ResearchGate

Esta versão evita scraping automático direto dessas plataformas. O Lattes é integrado como link oficial de cada docente. Google Scholar e ResearchGate podem ser adicionados posteriormente por importação autorizada (CSV/BibTeX) ou por uma fonte/API compatível com seus termos de uso.

## Próximas extensões recomendadas

- Cadastro manual do OpenAlex ID/ORCID de cada docente para eliminar homônimos.
- Importador CSV/BibTeX do Google Scholar.
- Importador de XML/Currículo Lattes obtido por meio autorizado.
- Integração Crossref para validação/enriquecimento de DOI.
- Exportação em Excel, CSV e PDF.
- Filtro por instituição.
- Página pública hospedada em Streamlit Community Cloud, Render ou servidor institucional.
