import type { HTMLAttributes, SVGProps } from 'react'

type LogoVariant = 'full' | 'icon' | 'white'

function PilotMark({ monochrome = false, ...props }: SVGProps<SVGSVGElement> & { monochrome?: boolean }) {
  return <svg viewBox="0 0 40 40" aria-hidden="true" focusable="false" {...props}>
    <rect className="pilot-mark-bg" x="1" y="1" width="38" height="38" rx="11" />
    {/* La pointe et le fuselage donnent la direction nord-est ; les trois traits forment l'aile. */}
    <path className="pilot-mark-plane" d="M10 24.8 30.5 8.5 22.2 30.2 17.4 22.8Z" />
    <path className="pilot-mark-cut" d="m17.4 22.8 13.1-14.3" />
    <path className="pilot-mark-wing" d="M7.2 27.8h4.2M7.2 23.3h6.7M7.2 18.8h9.2" />
    {!monochrome && <path className="pilot-mark-accent" d="M25.4 10.5 30.5 8.5 28.6 13.5Z" />}
  </svg>
}

/** Logo FinPilot réutilisable : complet, icône seule, ou version monochrome blanche. */
export function Logo({ variant = 'full', className = '', ...props }: {
  variant?: LogoVariant
  className?: string
} & HTMLAttributes<HTMLSpanElement>) {
  const white = variant === 'white'
  return <span className={`finpilot-logo ${white ? 'finpilot-logo--white' : ''} ${className}`.trim()} role={variant === 'icon' ? 'img' : undefined} aria-label={variant === 'icon' ? 'FinPilot' : undefined} {...props}>
    <PilotMark className="finpilot-logo__mark" monochrome={white} />
    {variant !== 'icon' && <span className="finpilot-logo__word"><span>Fin</span><strong>Pilot</strong></span>}
  </span>
}
