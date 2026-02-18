"""
Modulo de analise de documentos para deteccao de fraude usando Azure AI.
Utiliza Azure Document Intelligence para extracao e Azure OpenAI para analise.
"""

import os
import json
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential
except ImportError:
    DocumentIntelligenceClient = None
    AzureKeyCredential = None

try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None

load_dotenv()


class DocumentAnalyzer:
    """Analisa documentos para deteccao de fraude usando Azure Document Intelligence."""

    def __init__(self):
        self.doc_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        self.doc_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.openai_key = os.getenv("AZURE_OPENAI_KEY")
        self.openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

        self.doc_client = None
        self.openai_client = None

        if self.doc_key and self.doc_endpoint and DocumentIntelligenceClient:
            self.doc_client = DocumentIntelligenceClient(
                endpoint=self.doc_endpoint,
                credential=AzureKeyCredential(self.doc_key),
            )

        if self.openai_key and self.openai_endpoint and AzureOpenAI:
            self.openai_client = AzureOpenAI(
                api_key=self.openai_key,
                api_version="2024-02-01",
                azure_endpoint=self.openai_endpoint,
            )

    def analyze_document(self, document_path: str) -> dict:
        """
        Analisa um documento para extracao de dados e deteccao de fraude.

        Args:
            document_path: Caminho do arquivo do documento

        Returns:
            Dicionario com dados extraidos e analise de fraude
        """
        extracted_data = self._extract_document_data(document_path)
        validation_results = self._validate_fields(extracted_data)
        fraud_analysis = self._analyze_fraud_patterns(extracted_data, validation_results)

        risk_score = self._calculate_risk_score(validation_results, fraud_analysis)

        return {
            "timestamp": datetime.now().isoformat(),
            "document": document_path,
            "extracted_data": extracted_data,
            "validation": validation_results,
            "fraud_analysis": fraud_analysis,
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
        }

    def _extract_document_data(self, document_path: str) -> dict:
        """Extrai dados estruturados do documento usando Azure Document Intelligence."""
        if not self.doc_client:
            return {"error": "Document Intelligence client nao configurado"}

        with open(document_path, "rb") as f:
            poller = self.doc_client.begin_analyze_document(
                "prebuilt-document", body=f
            )
            result = poller.result()

        extracted = {
            "key_value_pairs": {},
            "tables": [],
            "entities": [],
        }

        if result.key_value_pairs:
            for pair in result.key_value_pairs:
                key = pair.key.content if pair.key else "unknown"
                value = pair.value.content if pair.value else ""
                extracted["key_value_pairs"][key] = value

        if result.tables:
            for table in result.tables:
                table_data = []
                for cell in table.cells:
                    table_data.append({
                        "row": cell.row_index,
                        "col": cell.column_index,
                        "content": cell.content,
                    })
                extracted["tables"].append(table_data)

        return extracted

    def _validate_fields(self, extracted_data: dict) -> dict:
        """Valida os campos extraidos do documento."""
        results = {"valid_fields": [], "invalid_fields": [], "warnings": []}

        kvp = extracted_data.get("key_value_pairs", {})

        for key, value in kvp.items():
            key_lower = key.lower()
            if "cpf" in key_lower:
                if self._validate_cpf(value):
                    results["valid_fields"].append(f"CPF: {value}")
                else:
                    results["invalid_fields"].append(f"CPF invalido: {value}")
            elif "cnpj" in key_lower:
                if self._validate_cnpj(value):
                    results["valid_fields"].append(f"CNPJ: {value}")
                else:
                    results["invalid_fields"].append(f"CNPJ invalido: {value}")
            elif "data" in key_lower or "date" in key_lower:
                if self._validate_date(value):
                    results["valid_fields"].append(f"Data: {value}")
                else:
                    results["warnings"].append(f"Data suspeita: {value}")

        return results

    def _validate_cpf(self, cpf: str) -> bool:
        """Valida numero de CPF brasileiro."""
        cpf = "".join(filter(str.isdigit, cpf))
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False

        for i in range(9, 11):
            total = sum(int(cpf[j]) * ((i + 1) - j) for j in range(i))
            digit = (total * 10 % 11) % 10
            if int(cpf[i]) != digit:
                return False
        return True

    def _validate_cnpj(self, cnpj: str) -> bool:
        """Valida numero de CNPJ brasileiro."""
        cnpj = "".join(filter(str.isdigit, cnpj))
        if len(cnpj) != 14:
            return False
        return True

    def _validate_date(self, date_str: str) -> bool:
        """Valida se a data e valida e nao esta no futuro."""
        formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"]
        for fmt in formats:
            try:
                date = datetime.strptime(date_str.strip(), fmt)
                return date <= datetime.now()
            except ValueError:
                continue
        return False

    def _analyze_fraud_patterns(self, extracted_data: dict, validation: dict) -> dict:
        """Analisa padroes de fraude usando Azure OpenAI."""
        if not self.openai_client:
            return {"analysis": "OpenAI client nao configurado", "flags": []}

        prompt = f"""Analise os seguintes dados extraidos de um documento e identifique possiveis indicadores de fraude:

Dados extraidos: {json.dumps(extracted_data.get('key_value_pairs', {}), ensure_ascii=False)}
Validacao: {json.dumps(validation, ensure_ascii=False)}

Forneca uma analise estruturada com:
1. Indicadores de fraude encontrados
2. Nivel de suspeita (baixo, medio, alto)
3. Recomendacoes"""

        response = self.openai_client.chat.completions.create(
            model=self.openai_deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        return {
            "analysis": response.choices[0].message.content,
            "flags": validation.get("invalid_fields", []),
        }

    def _calculate_risk_score(self, validation: dict, fraud_analysis: dict) -> int:
        """Calcula score de risco de 0 a 100."""
        score = 0
        invalid_count = len(validation.get("invalid_fields", []))
        warning_count = len(validation.get("warnings", []))
        flag_count = len(fraud_analysis.get("flags", []))

        score += invalid_count * 25
        score += warning_count * 10
        score += flag_count * 15

        return min(score, 100)

    def _get_risk_level(self, score: int) -> str:
        """Retorna o nivel de risco baseado no score."""
        if score <= 20:
            return "BAIXO"
        elif score <= 50:
            return "MEDIO"
        elif score <= 75:
            return "ALTO"
        return "CRITICO"


if __name__ == "__main__":
    analyzer = DocumentAnalyzer()
    print("Document Analyzer inicializado com sucesso.")
