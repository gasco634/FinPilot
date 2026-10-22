import { useEffect, useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ArrowRight, LockKeyhole, Moon, Sun } from 'lucide-react'
import { api, setToken } from '../lib/api'
import { Button, ErrorState } from '../components/ui'
import { Logo } from '../components/Logo'
import { DeveloperSignature } from '../components/DeveloperSignature'

type AuthMode = 'login' | 'register'

export function Login({ onLogin }: { onLogin: () => void }) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [dark, setDark] = useState(() => localStorage.getItem('finpilot_theme') === 'dark')
  const [portraitFailed, setPortraitFailed] = useState(false)
  const [validationError, setValidationError] = useState('')
  const mutation = useMutation({
    mutationFn: () => api<{ access_token: string }>(mode === 'register' ? '/auth/register' : '/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: email.trim(), password }),
    }),
    onSuccess: data => { setToken(data.access_token); onLogin() },
  })

  // La connexion partage le même thème persistant que le reste de l'application.
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('finpilot_theme', dark ? 'dark' : 'light')
  }, [dark])

  function switchMode() {
    setMode(value => value === 'login' ? 'register' : 'login')
    setPassword('')
    setConfirmPassword('')
    setValidationError('')
    mutation.reset()
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedEmail = email.trim()
    if (!normalizedEmail) { setValidationError('Saisissez votre adresse e-mail.'); return }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) { setValidationError('Vérifiez le format de votre adresse e-mail.'); return }
    if (!password) { setValidationError('Saisissez votre mot de passe.'); return }
    if (mode === 'register') {
      if (password.length < 8) { setValidationError('Choisissez un mot de passe d’au moins 8 caractères.'); return }
      if (new TextEncoder().encode(password).length > 72) { setValidationError('Le mot de passe ne doit pas dépasser 72 octets.'); return }
      if (password !== confirmPassword) { setValidationError('Les deux mots de passe ne correspondent pas.'); return }
    }
    setValidationError('')
    mutation.mutate()
  }

  const registering = mode === 'register'

  return <main className="login-screen">
    <section className="login-panel" aria-labelledby="login-heading">
      <div className="login-panel-top">
        <Logo />
        <button className="login-theme-toggle" type="button" onClick={() => setDark(value => !value)} aria-label={dark ? 'Activer le mode jour' : 'Activer le mode nuit'} title={dark ? 'Mode jour' : 'Mode nuit'}>
          {dark ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>

      <form className="login-form" onSubmit={submit} noValidate>
        <div className="login-kicker">VOTRE ESPACE FINANCIER</div>
        <h1 id="login-heading">{registering ? 'Créez votre compte' : 'Connectez-vous'}</h1>
        <p className="login-intro">{registering ? 'Votre espace démarre sans client ni chiffre prérempli.' : 'Retrouvez vos revenus, vos dépenses et les décisions à prendre.'}</p>

        <label className="login-field" htmlFor="login-email">Adresse e-mail
          <input id="login-email" type="email" value={email} onChange={event => { setEmail(event.target.value); setValidationError(''); mutation.reset() }} required autoComplete="username" placeholder="nom@exemple.com" aria-describedby={validationError || mutation.error ? 'login-error' : undefined} />
        </label>
        <label className="login-field" htmlFor="login-password">Mot de passe
          <div className="login-password-wrap">
            <input id="login-password" type="password" value={password} onChange={event => { setPassword(event.target.value); setValidationError(''); mutation.reset() }} required minLength={registering ? 8 : undefined} autoComplete={registering ? 'new-password' : 'current-password'} placeholder={registering ? '8 caractères minimum' : 'Votre mot de passe'} aria-describedby={validationError || mutation.error ? 'login-error' : undefined} />
            <LockKeyhole size={16} aria-hidden="true" />
          </div>
        </label>
        {registering && <label className="login-field" htmlFor="login-password-confirm">Confirmez le mot de passe
          <div className="login-password-wrap">
            <input id="login-password-confirm" type="password" value={confirmPassword} onChange={event => { setConfirmPassword(event.target.value); setValidationError(''); mutation.reset() }} required autoComplete="new-password" placeholder="Saisissez-le une seconde fois" aria-describedby={validationError || mutation.error ? 'login-error' : undefined} />
            <LockKeyhole size={16} aria-hidden="true" />
          </div>
        </label>}
        {(validationError || mutation.error) && <div id="login-error" role="alert">{validationError ? <p className="login-validation-error">{validationError}</p> : <ErrorState error={mutation.error} />}</div>}
        <Button type="submit" className="login-submit" disabled={mutation.isPending}>
          {mutation.isPending ? (registering ? 'Création…' : 'Connexion…') : <>{registering ? 'Créer mon espace' : 'Ouvrir mon espace'} <ArrowRight size={16} /></>}
        </Button>

        <p className="login-mode-switch">
          {registering ? 'Vous avez déjà un compte ? ' : 'Pas encore de compte ? '}
          <button type="button" onClick={switchMode}>{registering ? 'Se connecter' : 'Créer un compte'}</button>
        </p>
        <p className="login-privacy">Chaque compte dispose de son propre espace financier.</p>
      </form>

      <DeveloperSignature className="login-signature" />
    </section>

    <section className="login-portrait" aria-label="Présentation de FinPilot">
      <div className="portrait-orb portrait-orb--large" aria-hidden="true" />
      <div className="portrait-orb portrait-orb--small" aria-hidden="true" />
      <div className="portrait-copy">
        <span className="portrait-eyebrow">PILOTEZ AVEC CONFIANCE</span>
        <h2>La clarté<br />change la trajectoire.</h2>
        <p>Un cockpit simple pour avancer avec des chiffres lisibles et des choix éclairés.</p>
      </div>

      <figure className={`portrait-frame ${portraitFailed ? 'portrait-frame--fallback' : ''}`}>
        {!portraitFailed
          ? <img src="/assets/jeremie.webp" alt="Portrait de Jérémie GASBEOGO, développeur de FinPilot" loading="lazy" decoding="async" onError={() => setPortraitFailed(true)} />
          : <div className="portrait-fallback" role="img" aria-label="Initiales de Jérémie GASBEOGO sur fond bleu dégradé">JG</div>}
        <figcaption className="portrait-caption">Jérémie GASBEOGO <span>· FinPilot</span></figcaption>
      </figure>

      <div className="demo-float demo-float--revenue"><span className="demo-float__eyebrow">REVENUS · DÉMO</span><strong>+12 %</strong><small>vs période précédente</small></div>
      <div className="demo-float demo-float--savings"><span className="demo-float__eyebrow">ÉPARGNE · DÉMO</span><strong>340 000 <small>FCFA</small></strong><small>objectif mensuel</small></div>
      <div className="demo-float demo-float--invoices"><span className="demo-float__dot" /> FACTURES · DÉMO <b>À jour</b></div>
      <span className="portrait-note">Les cartes affichent des données fictives.</span>
    </section>
  </main>
}
