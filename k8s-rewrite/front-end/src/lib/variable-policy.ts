export function isSensitiveVariable(variable: {
  key: string;
  category: string;
  encrypted: boolean;
}) {
  return (
    variable.encrypted ||
    ["secret", "system"].includes(variable.category) ||
    variable.key.startsWith("secret_") ||
    /(?:^|_)(?:password|token|secret)(?:_|$)/i.test(variable.key) ||
    /private_key(?!_file)/i.test(variable.key)
  );
}
