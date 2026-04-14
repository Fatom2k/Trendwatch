/**
 * Auth0 Action — Whitelist par email
 *
 * À coller dans : Auth0 Dashboard → Actions → Library → Create Action
 * Trigger : Login / Post Login
 *
 * Fonctionnement :
 * - Si l’email de l’utilisateur n’est pas dans ALLOWED_EMAILS ou ADMIN_EMAILS,
 *   Auth0 bloque la connexion AVANT même que le token soit émis.
 * - Configurer les emails dans Actions → Secrets (recommandé) ou en dur ci-dessous.
 *
 * Secrets à créer dans Auth0 (Actions → Library → ton action → Secrets) :
 *   ADMIN_EMAILS   → "email1@gmail.com,email2@gmail.com"
 *   ALLOWED_EMAILS → "viewer1@gmail.com,viewer2@gmail.com"
 */
exports.onExecutePostLogin = async (event, api) => {
  const email = (event.user.email || '').toLowerCase().trim();

  const adminEmails = (event.secrets.ADMIN_EMAILS || '')
    .split(',')
    .map(e => e.trim().toLowerCase())
    .filter(Boolean);

  const allowedEmails = (event.secrets.ALLOWED_EMAILS || '')
    .split(',')
    .map(e => e.trim().toLowerCase())
    .filter(Boolean);

  const allAuthorized = [...new Set([...adminEmails, ...allowedEmails])];

  // Si aucune liste configurée → accès ouvert (désactiver en production)
  if (allAuthorized.length === 0) return;

  if (!allAuthorized.includes(email)) {
    api.access.deny(
      `Accès refusé : l’adresse ${email} n’est pas autorisée.`
    );
  }
};
