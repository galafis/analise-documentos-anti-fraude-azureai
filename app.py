"""
Dashboard Streamlit para analise de documentos anti-fraude com Azure AI.
"""

import streamlit as st
import json
import tempfile
import os
from src.document_analyzer import DocumentAnalyzer


def main():
    st.set_page_config(
        page_title="Analise Anti-fraude - Azure AI",
        page_icon="\ud83d\udd0d",
        layout="wide",
    )

    st.title("Analise de Documentos Anti-fraude com Azure AI")
    st.markdown("Sistema de deteccao de fraude em documentos usando Azure Document Intelligence e OpenAI.")

    uploaded_file = st.file_uploader(
        "Faca upload do documento para analise",
        type=["pdf", "png", "jpg", "jpeg", "tiff"],
    )

    if uploaded_file and st.button("Analisar Documento", type="primary"):
        try:
            analyzer = DocumentAnalyzer()

            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            with st.spinner("Analisando documento..."):
                result = analyzer.analyze_document(tmp_path)

            os.unlink(tmp_path)

            col1, col2, col3 = st.columns(3)

            with col1:
                score = result["risk_score"]
                color = "green" if score <= 20 else "orange" if score <= 50 else "red"
                st.metric("Score de Risco", f"{score}/100")

            with col2:
                st.metric("Nivel de Risco", result["risk_level"])

            with col3:
                valid = len(result["validation"]["valid_fields"])
                invalid = len(result["validation"]["invalid_fields"])
                st.metric("Campos Validos/Invalidos", f"{valid}/{invalid}")

            st.subheader("Detalhes da Validacao")

            if result["validation"]["valid_fields"]:
                st.success("Campos validos: " + ", ".join(result["validation"]["valid_fields"]))

            if result["validation"]["invalid_fields"]:
                st.error("Campos invalidos: " + ", ".join(result["validation"]["invalid_fields"]))

            if result["validation"]["warnings"]:
                st.warning("Alertas: " + ", ".join(result["validation"]["warnings"]))

            st.subheader("Analise de Fraude")
            st.write(result["fraud_analysis"].get("analysis", "Analise nao disponivel"))

            st.subheader("Dados Extraidos")
            st.json(result["extracted_data"])

            st.download_button(
                label="Exportar Relatorio (JSON)",
                data=json.dumps(result, ensure_ascii=False, indent=2),
                file_name="relatorio_antifraude.json",
                mime="application/json",
            )

        except Exception as e:
            st.error(f"Erro na analise: {e}")


if __name__ == "__main__":
    main()
