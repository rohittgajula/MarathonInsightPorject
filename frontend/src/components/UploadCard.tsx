import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { invalidateTrainingData } from "../lib/queryKeys";
import type { Activity } from "../lib/types";

interface UploadResult { activity: Activity | null; detail?: string; }

export function UploadCard() {
  const input = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.post<UploadResult>("/uploads/", form);
    },
    onSuccess: (result) => {
      invalidateTrainingData(queryClient);
      if (result.detail) setMessage(result.detail);
      if (result.activity) navigate(`/activity/${result.activity.id}`);
    },
    onError: (err: Error) => setMessage(err.message),
  });

  return (
    <div className="card stack" style={{ gap: 10 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Add a run</h2>
          <p className="faint" style={{ margin: "3px 0 0" }}>
            Export a <code>.fit</code> file from Garmin Connect and drop it here.
          </p>
        </div>
        <div className="row">
          <input
            ref={input} type="file" accept=".fit" style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              setMessage(null);
              if (file) upload.mutate(file);
              e.target.value = "";
            }}
          />
          <button onClick={() => input.current?.click()} disabled={upload.isPending}>
            {upload.isPending ? "Parsing…" : "Upload .fit"}
          </button>
        </div>
      </div>
      {message && <p className="error" style={{ margin: 0 }}>{message}</p>}
    </div>
  );
}
