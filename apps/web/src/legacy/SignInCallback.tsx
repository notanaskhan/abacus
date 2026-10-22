import { Alert, Button, Spinner } from "@abacus/ui";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useEffect, useRef, useState } from "react";
import { completeSignIn, signIn } from "../auth/session";

export function SignInCallback(): JSX.Element {
  const navigate = useNavigate();
  const [failed, setFailed] = useState(false);
  const started = useRef(false); // the code is single use: exchange it once, even in StrictMode

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    completeSignIn(window.location.search).then(
      (returnTo) => void navigate({ to: returnTo, replace: true }),
      () => {
        setFailed(true);
      },
    );
  }, [navigate]);

  if (failed) {
    return (
      <main className="mx-auto max-w-md p-8">
        <Alert
          title="Sign-in didn't complete"
          action={
            <Button size="sm" onClick={() => void signIn("/")}>
              Sign in again
            </Button>
          }
        >
          The response from the sign-in page couldn't be used.
        </Alert>
      </main>
    );
  }
  return (
    <main className="p-8">
      <Spinner label="Signing you in…" />
    </main>
  );
}
