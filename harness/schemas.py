"""Output contract and instructions of every agent stage. The controller validates each result."""
from __future__ import annotations


def _obj(required_fields, **properties):
    return {"type": "object", "additionalProperties": False, "required": list(required_fields), "properties": properties}


STR = {"type": "string"}
TEXT = {"type": "string", "minLength": 1}
STRS = {"type": "array", "items": TEXT}
SCORE = {"type": "number", "minimum": 0, "maximum": 1}
RISK = {"type": "string", "enum": ["low", "medium", "high"]}
SHA = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
QUESTIONS = {"type": "array", "items": TEXT, "maxItems": 3}

STAGES = {
    "pm": {
        "instructions": "Avalie a issue como PM: problema, quem é afetado, escopo dentro e fora, e critérios de aceite "
                        "verificáveis. Leia o código só para entender o comportamento atual. Classifique o escopo "
                        "(screen = tela nova; ui_change = mudança em tela existente). Pergunte apenas o que muda o que "
                        "será construído e não pode ser inferido.",
        "schema": _obj(["summary", "scope_type", "complexity", "requires_plan_approval", "acceptance_criteria", "questions"],
                       summary=TEXT, scope_type={"enum": ["screen", "ui_change", "backend", "other"]},
                       complexity={"enum": ["simple", "complex"]}, requires_plan_approval={"type": "boolean"},
                       acceptance_criteria=STRS, questions=QUESTIONS),
    },
    "research": {
        "instructions": "Pesquise o código para a decisão do PM: arquivos e padrões parecidos, convenções e comandos de "
                        "teste exatos. Para um bug, investigue a causa provável. Não proponha o plano.",
        "schema": _obj(["summary", "kind", "relevant_files", "patterns", "test_commands"],
                       summary=TEXT, kind={"enum": ["bug", "feature", "chore"]}, relevant_files=STRS,
                       patterns=STRS, test_commands=STRS),
    },
    "design_need": {
        "instructions": "Decida se a mudança precisa de design antes do plano. Tela nova sempre precisa. Mudanças que "
                        "reaproveitam a interface existente não precisam. Se precisar, escreva o briefing do Designer.",
        "schema": _obj(["summary", "needed", "confidence", "design_brief"],
                       summary=TEXT, needed={"type": "boolean"}, confidence=SCORE, design_brief=STR),
    },
    "design": {
        "instructions": "Crie três opções de design distintas para o briefing, usando componentes de packages/ui e "
                        "padrões existentes. Cada mockup é um esboço em texto (ASCII) com os estados principais. "
                        "Recomende uma opção.",
        "schema": _obj(["summary", "recommended_option", "options"],
                       summary=TEXT, recommended_option={"type": "integer", "minimum": 1, "maximum": 3},
                       options={"type": "array", "minItems": 3, "maxItems": 3, "items": _obj(
                           ["id", "title", "summary", "mockup"], id={"type": "integer", "minimum": 1, "maximum": 3},
                           title=TEXT, summary=TEXT, mockup=TEXT)}),
    },
    "plan": {
        "instructions": "Escreva o plano de implementação a partir da issue, da decisão do PM, da pesquisa e do design "
                        "escolhido, se houver. Liste todos os arquivos que serão alterados, os testes e os critérios de "
                        "aceite. Respeite `scope`. Se houver `evaluation_feedback` ou `owner_feedback`, corrija o plano.",
        "schema": _obj(["summary", "files", "tests", "acceptance_criteria", "steps", "risk", "open_questions"],
                       summary=TEXT, files={"type": "array", "minItems": 1, "items": TEXT},
                       tests={"type": "array", "items": _obj(["path", "kind", "purpose"], path=TEXT,
                                                              kind={"enum": ["new_test", "existing_test"]}, purpose=TEXT)},
                       acceptance_criteria={"type": "array", "minItems": 1, "items": TEXT}, steps=STRS, risk=RISK,
                       open_questions=QUESTIONS),
    },
    "evaluate": {
        "instructions": "Avalie a aderência do plano ao pedido (issue e decisão do PM) e ao design escolhido. Confira se "
                        "cada critério de aceite do PM está coberto por um teste. Não reescreva o plano.",
        "schema": _obj(["summary", "aligned", "score", "risk", "requires_human", "missing_acceptance_criteria", "findings"],
                       summary=TEXT, aligned={"type": "boolean"}, score=SCORE, risk=RISK,
                       requires_human={"type": "boolean"}, missing_acceptance_criteria=STRS, findings=STRS),
    },
    "implement": {
        "instructions": "Implemente o plano aprovado alterando somente `plan.files`. Rode os comandos de teste do plano. "
                        "Não faça commit: o controlador valida e publica o diff. Se houver `failed_checks` ou "
                        "`test_findings`, corrija exatamente essas falhas sem mudar o plano.",
        "schema": _obj(["summary", "files", "verification"], summary=TEXT, files=STRS, verification=STRS),
    },
    "test": {
        "instructions": "Confira cada critério de aceite contra o diff e as evidências reais da CI do commit `head_sha` "
                        "(comandos, códigos de saída, saída). Avalie se há teste cobrindo cada critério. Não invente "
                        "resultados; uma lacuna é um achado.",
        "schema": _obj(["summary", "head_sha", "passed", "coverage", "findings"],
                       summary=TEXT, head_sha=SHA, passed={"type": "boolean"},
                       coverage={"type": "array", "items": _obj(["criterion", "covered", "evidence"], criterion=TEXT,
                                                                covered={"type": "boolean"}, evidence=TEXT)},
                       findings=STRS),
    },
    "code_evals": {
        "instructions": "Avalie o diff do commit `head_sha` em três eixos independentes: complexidade da mudança, "
                        "aderência ao plano aprovado e estilo do código em relação aos padrões vizinhos. Recomende "
                        "review humano quando houver risco.",
        "schema": _obj(["summary", "head_sha", "complexity", "plan_adherence", "style", "human_review"],
                       summary=TEXT, head_sha=SHA,
                       complexity=_obj(["level", "reasons"], level={"enum": ["low", "medium", "high"]}, reasons=STRS),
                       plan_adherence=_obj(["passed", "score", "findings"], passed={"type": "boolean"}, score=SCORE, findings=STRS),
                       style=_obj(["passed", "findings"], passed={"type": "boolean"}, findings=STRS),
                       human_review=_obj(["required", "reasons"], required={"type": "boolean"}, reasons=STRS)),
    },
    "review": {
        "instructions": "Revise de forma independente o diff do commit `head_sha` contra a issue, o plano e as evidências: "
                        "bugs, casos de borda, segurança (autorização, validação, exposição de dados) e encaixe nos "
                        "padrões. Liste só o que precisa mudar antes do merge.",
        "schema": _obj(["summary", "head_sha", "aligned", "score", "risk", "findings"],
                       summary=TEXT, head_sha=SHA, aligned={"type": "boolean"}, score=SCORE, risk=RISK, findings=STRS),
    },
    "deploy": {
        "instructions": "Avalie a versão integrada `merge_sha`: as evidências da CI do main, os critérios de aceite e o "
                        "que a entrega exige (migrações, variáveis de ambiente, flags). Diga se a entrega está concluída "
                        "ou se é preciso reverter.",
        "schema": _obj(["summary", "merge_sha", "passed", "findings"], summary=TEXT, merge_sha=SHA,
                       passed={"type": "boolean"}, findings=STRS),
    },
}
STAGES["repair"] = STAGES["implement"]
