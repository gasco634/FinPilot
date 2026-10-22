const developerUrl = import.meta.env.VITE_DEVELOPER_URL?.trim()
const whatsappNumber = import.meta.env.VITE_WHATSAPP_NUMBER?.replace(/\D/g, '')
const signatureHref = developerUrl || (whatsappNumber ? `https://wa.me/${whatsappNumber}` : undefined)

/** Une seule signature, partagée par la connexion et le pied de page applicatif. */
export function DeveloperSignature({ className = '' }: { className?: string }) {
  const label = 'Conçu et développé par Jérémie GASBEOGO'
  return <span className={`developer-signature ${className}`.trim()}>
    {signatureHref
      ? <a href={signatureHref} target="_blank" rel="noreferrer">{label}</a>
      : <span title="Configurez VITE_WHATSAPP_NUMBER ou VITE_DEVELOPER_URL pour activer le lien">{label}</span>}
  </span>
}
