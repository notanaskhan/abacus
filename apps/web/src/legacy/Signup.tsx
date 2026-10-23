import { signupMutation } from "@abacus/api-client/query";
import { Alert, Button, Card, Input, Label, Spinner } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";
import { chooseTenant, useSignedIn } from "../app-core/auth";

const REFUSALS: Record<string, string> = {
  signup_code_invalid: "That sign-up code isn't valid. It may have been used or have expired.",
  signup_already_staff:
    "You already belong to a firm on Accrued. Ask your administrator if you need another.",
  signup_rate_limited: "Too many attempts. Please wait an hour and try again.",
  signup_invalid: "Your sign-in has no verified email, or the firm name isn't valid.",
};

/** SPEC-024 AC-1: a firm administrator sets up their firm with a sign-up code. */
export function Signup(): JSX.Element {
  const signedIn = useSignedIn("/signup");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const create = useMutation({
    ...signupMutation(),
    onSuccess: (data) => {
      chooseTenant(data.tenant_id);
      void queryClient.invalidateQueries();
      void navigate({ to: "/" });
    },
  });
  if (!signedIn) return <Spinner label="Signing you in…" />;
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    create.mutate({ body: { firm_name: name.trim(), code: code.trim() } });
  };
  const failure = create.isError ? errorMessage(create.error) : null;
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 bg-shell p-6">
      <Card className="flex flex-col gap-4">
        <div>
          <h1 className="text-dashboard">Set up your firm</h1>
          <p className="text-body text-ink-3">
            You&apos;ll be its first administrator. Next, you&apos;ll connect sign-on, invite your
            team and upload your methodology.
          </p>
        </div>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <div className="flex flex-col gap-1">
            <Label htmlFor="firm-name">Firm name</Label>
            <Input
              id="firm-name"
              required
              maxLength={200}
              value={name}
              onChange={(event) => {
                setName(event.target.value);
              }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="signup-code">Sign-up code</Label>
            <Input
              id="signup-code"
              required
              autoComplete="off"
              placeholder="ABCD-EFGH-JKMN-PQRS"
              value={code}
              onChange={(event) => {
                setCode(event.target.value);
              }}
            />
          </div>
          {failure !== null && (
            <p role="alert" className="text-body text-danger">
              {REFUSALS[failure] ?? failure}
            </p>
          )}
          <Button
            type="submit"
            disabled={create.isPending || name.trim() === "" || code.trim() === ""}
          >
            {create.isPending ? "Setting up…" : "Create firm"}
          </Button>
        </form>
      </Card>
      <p className="text-center text-body text-ink-3">
        Joining an existing firm? Ask its administrator to invite you.{" "}
        <Link to="/" className="text-espresso hover:underline">
          Back
        </Link>
      </p>
    </main>
  );
}

/** Signed in, but not on any firm's staff and not a client contact (SPEC-024 §6). */
export function NoFirm(): JSX.Element {
  return (
    <main className="mx-auto max-w-md p-8">
      <Alert title="You're not part of a firm yet">
        If your firm already uses Accrued, ask its administrator to invite you. Setting up a new
        firm?{" "}
        <Link to="/signup" className="font-medium text-espresso hover:underline">
          Set up your firm
        </Link>
      </Alert>
    </main>
  );
}
