export default function LoginPage() {
  return (
    <div className="card card-pad" style={{ maxWidth: 430, margin: "12vh auto" }}>
      <div className="eyebrow">Identidade institucional</div>
      <h1>Acesse o Investing OS</h1>
      <p className="subtitle">
        A sessão usa o provedor OIDC configurado pela organização. Permissões continuam validadas
        pela API.
      </p>
      <a
        className="button"
        href="/api/auth/login"
        style={{ display: "inline-block", marginTop: 22 }}
      >
        Continuar com SSO
      </a>
    </div>
  );
}
