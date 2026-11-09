export type SanctumFeed = {
  mode: "poll" | "realtime";
  close: () => void;
};

type SupabaseEnv = {
  url?: string;
  anonKey?: string;
};

function jwtRole(token: string): string | null {
  const parts = token.split(".");
  if (parts.length < 2) {
    return null;
  }
  try {
    const padded = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = JSON.parse(atob(padded)) as { role?: unknown };
    return typeof json.role === "string" ? json.role : null;
  } catch {
    return null;
  }
}

export function supabaseBlocked(env: SupabaseEnv): "missing" | "service_role" | null {
  if (!env.url || !env.anonKey) {
    return "missing";
  }
  if (env.anonKey.includes("service_role") || jwtRole(env.anonKey) === "service_role") {
    return "service_role";
  }
  return null;
}

export async function openSanctumChannel(
  env: SupabaseEnv,
  onEvent: (payload: unknown) => void,
): Promise<SanctumFeed> {
  if (supabaseBlocked(env) !== null || !env.url || !env.anonKey) {
    return { mode: "poll", close() {} };
  }
  const { createClient } = await import("@supabase/supabase-js");
  const client = createClient(env.url, env.anonKey, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
  const channel = client
    .channel("sanctum-status")
    .on("broadcast", { event: "desk" }, (message) => {
      onEvent(message);
    })
    .subscribe();
  return {
    mode: "realtime",
    close() {
      void client.removeChannel(channel);
    },
  };
}
