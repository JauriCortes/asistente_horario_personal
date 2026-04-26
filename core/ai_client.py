import os
import re
import shlex
import subprocess
import yaml
from pathlib import Path


def _resolve_env_vars(value: str) -> str:
    return re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1), m.group(0)),
        value,
    )


def _resolve_config(obj):
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_config(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_config(i) for i in obj]
    return obj


def _strip_markdown_code_block(text: str) -> str:
    """Los CLIs a veces envuelven el JSON en ```json ... ```. Lo quitamos."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()
    return text


def _build_cli_prompt(
    messages: list[dict],
    system_prompt: str | None,
    json_mode: bool,
) -> str:
    parts = []
    if system_prompt:
        parts.append(system_prompt)
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "assistant":
            parts.append(f"[Respuesta anterior]\n{content}")
        else:
            parts.append(content)
    if json_mode:
        parts.append(
            "IMPORTANTE: Responde ÚNICAMENTE con JSON válido. "
            "Sin texto adicional, sin bloques de código markdown, solo el JSON."
        )
    return "\n\n".join(parts)


class AIClient:
    def __init__(self, config_path: str | None = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        self._config = _resolve_config(raw)
        self._sdk_clients: dict = {}

    def _get_sdk_client(self, provider_name: str):
        if provider_name in self._sdk_clients:
            return self._sdk_clients[provider_name]
        provider = self._config["providers"][provider_name]
        ptype = provider["type"]
        if ptype == "openai_compatible":
            from openai import OpenAI
            client = OpenAI(
                base_url=provider.get("api_base", "https://api.openai.com/v1"),
                api_key=provider.get("api_key", "none"),
            )
        elif ptype == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=provider["api_key"])
        elif ptype == "cli":
            client = None
        else:
            raise ValueError(f"Tipo de proveedor no soportado: {ptype}")
        self._sdk_clients[provider_name] = (ptype, client)
        return self._sdk_clients[provider_name]

    def _role_config(self, role: str) -> dict:
        roles = self._config.get("roles", {})
        if role not in roles:
            raise ValueError(f"Rol no configurado en models.yaml: '{role}'")
        return roles[role]

    def complete(
        self,
        role: str,
        system_prompt: str,
        user_message: str,
        json_mode: bool = False,
    ) -> str:
        return self.complete_messages(
            role=role,
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
            json_mode=json_mode,
        )

    def complete_messages(
        self,
        role: str,
        messages: list[dict],
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> str:
        role_cfg = self._role_config(role)
        fallback_list = role_cfg.get("fallback", [])
        temperature = role_cfg.get("temperature", 0.1)
        max_tokens = role_cfg.get("max_tokens", 1024)

        errors = []
        for option in fallback_list:
            provider_name = option["provider"]
            model = option.get("model")
            try:
                result = self._call_provider(
                    provider_name=provider_name,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    messages=messages,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                )
                if len(errors) > 0:
                    skipped = ", ".join(
                        f"{e['provider']}({e['model'] or 'default'})" for e in errors
                    )
                    print(f"[ai_client] rol '{role}': fallback activado. Falló: {skipped}. Usando: {provider_name}({model or 'default'})")
                return result
            except Exception as e:
                errors.append({"provider": provider_name, "model": model, "error": str(e)})
                print(f"[ai_client] rol '{role}': {provider_name}({model or 'default'}) falló → {e}")
                continue

        raise RuntimeError(
            f"Todos los proveedores fallaron para el rol '{role}'.\n"
            + "\n".join(f"  {e['provider']}({e['model']}): {e['error']}" for e in errors)
        )

    def _call_provider(
        self,
        provider_name: str,
        model: str | None,
        temperature: float,
        max_tokens: int,
        messages: list[dict],
        system_prompt: str | None,
        json_mode: bool,
    ) -> str:
        ptype, client = self._get_sdk_client(provider_name)

        if ptype == "cli":
            return self._complete_cli(
                provider_name=provider_name,
                model=model,
                messages=messages,
                system_prompt=system_prompt,
                json_mode=json_mode,
            )

        if not model:
            raise ValueError(f"El proveedor '{provider_name}' requiere un modelo especificado en el fallback")

        if ptype == "openai_compatible":
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            kwargs = dict(
                model=model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        elif ptype == "anthropic":
            sys_prompt = system_prompt or ""
            if json_mode and "JSON" not in sys_prompt:
                sys_prompt += "\nResponde únicamente con JSON válido, sin texto adicional."
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=sys_prompt,
                messages=messages,
            )
            return response.content[0].text

        raise ValueError(f"Tipo de proveedor no implementado: {ptype}")

    def _complete_cli(
        self,
        provider_name: str,
        model: str | None,
        messages: list[dict],
        system_prompt: str | None,
        json_mode: bool,
    ) -> str:
        provider = self._config["providers"][provider_name]
        command = list(provider["command"])

        model_flag = provider.get("model_flag")
        if model_flag and model:
            command = command + [model_flag, model]

        full_prompt = _build_cli_prompt(messages, system_prompt, json_mode)
        timeout = provider.get("timeout", 120)
        input_mode = provider.get("input", "stdin")
        prompt_flag = provider.get("prompt_flag")

        if input_mode == "last_arg":
            suffix = [prompt_flag, full_prompt] if prompt_flag else [full_prompt]
            result = subprocess.run(
                command + suffix,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        else:
            result = subprocess.run(
                command,
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        output = result.stdout.strip()
        if not output and result.returncode != 0:
            raise RuntimeError(
                f"CLI '{' '.join(command)}' falló (código {result.returncode}):\n{result.stderr.strip()}"
            )
        if json_mode:
            output = _strip_markdown_code_block(output)
        return output


ai_client = AIClient()
