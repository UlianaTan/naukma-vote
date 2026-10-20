export function VoterLoading() {
  return <p role="status" className="py-8 text-muted-foreground">Завантаження…</p>;
}

export function VoterError({ message, retry }: { message: string; retry: () => void }) {
  return <div className="my-4 space-y-3">
    <p role="alert" className="rounded-md bg-destructive/10 p-4 text-destructive">{message}</p>
    <button onClick={retry} className="underline">Повторити перевірку</button>
  </div>;
}
