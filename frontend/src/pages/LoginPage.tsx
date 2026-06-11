import {
  Alert,
  Button,
  Card,
  Center,
  Code,
  List,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { QRCodeSVG } from "qrcode.react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText, setTokens } from "../api";
import { useAuth } from "../auth";

type Step = "credentials" | "totp_setup" | "recovery_codes";

export default function LoginPage() {
  const navigate = useNavigate();
  const { reload } = useAuth();
  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [setupToken, setSetupToken] = useState("");
  const [otpauthUri, setOtpauthUri] = useState("");
  const [secret, setSecret] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);

  async function finishLogin() {
    await reload();
    navigate("/");
  }

  async function submitCredentials(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/auth/login", {
        email,
        password,
        totp_code: totpCode || undefined,
      });
      if (data.status === "totp_setup_required") {
        setSetupToken(data.setup_token);
        const setup = await api.post(
          "/auth/totp/setup",
          {},
          { headers: { Authorization: `Bearer ${data.setup_token}` } },
        );
        setOtpauthUri(setup.data.otpauth_uri);
        setSecret(setup.data.secret);
        setTotpCode("");
        setStep("totp_setup");
      } else {
        setTokens(data.tokens.access_token, data.tokens.refresh_token);
        await finishLogin();
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitTotpSetup(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post(
        "/auth/totp/verify",
        { code: totpCode },
        { headers: { Authorization: `Bearer ${setupToken}` } },
      );
      setTokens(data.tokens.access_token, data.tokens.refresh_token);
      setRecoveryCodes(data.recovery_codes);
      setStep("recovery_codes");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Center h="100vh" bg="gray.0">
      <Card shadow="md" padding="xl" w={440}>
        <Title order={2} mb="md">
          GRC — вхід
        </Title>
        {error && (
          <Alert color="red" mb="md">
            {error}
          </Alert>
        )}

        {step === "credentials" && (
          <form onSubmit={submitCredentials}>
            <Stack>
              <TextInput
                label="Email"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
                required
                type="email"
              />
              <PasswordInput
                label="Пароль"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
              />
              <TextInput
                label="Код 2FA"
                description="Залиште порожнім при першому вході"
                value={totpCode}
                onChange={(e) => setTotpCode(e.currentTarget.value)}
                placeholder="123456"
              />
              <Button type="submit" loading={busy}>
                Увійти
              </Button>
            </Stack>
          </form>
        )}

        {step === "totp_setup" && (
          <form onSubmit={submitTotpSetup}>
            <Stack>
              <Text>
                Відскануйте QR-код у застосунку-автентифікаторі (Google Authenticator, Aegis
                тощо) та введіть код підтвердження.
              </Text>
              <Center>
                <QRCodeSVG value={otpauthUri} size={180} />
              </Center>
              <Text size="sm" c="dimmed">
                Або введіть секрет вручну: <Code>{secret}</Code>
              </Text>
              <TextInput
                label="Код підтвердження"
                value={totpCode}
                onChange={(e) => setTotpCode(e.currentTarget.value)}
                required
                placeholder="123456"
              />
              <Button type="submit" loading={busy}>
                Підтвердити та увійти
              </Button>
            </Stack>
          </form>
        )}

        {step === "recovery_codes" && (
          <Stack>
            <Alert color="yellow" title="Збережіть резервні коди">
              Кожен код можна використати один раз для входу, якщо ви втратите доступ до
              автентифікатора. Вони більше не будуть показані.
            </Alert>
            <List>
              {recoveryCodes.map((code) => (
                <List.Item key={code}>
                  <Code>{code}</Code>
                </List.Item>
              ))}
            </List>
            <Button onClick={() => void finishLogin()}>Продовжити</Button>
          </Stack>
        )}
      </Card>
    </Center>
  );
}
