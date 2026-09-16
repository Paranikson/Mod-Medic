import type { ValidateResponse } from "./types";

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function messageForStatus(status: number): string {
  if (status === 400) {
    return "Please upload a .zip file. In MCreator, choose File then Export workspace to ZIP.";
  }
  if (status === 413) {
    return 'That file is too big. Use MCreator\'s "Export workspace to ZIP" option rather than zipping the folder yourself.';
  }
  if (status === 422) {
    return "That zip doesn't look like an MCreator workspace. Export the workspace from MCreator and try that file.";
  }
  return "Something went wrong while checking the workspace. Please try again.";
}

export async function validateZip(file: File): Promise<ValidateResponse> {
  const body = new FormData();
  body.append("file", file);

  let response: Response;
  try {
    response = await fetch("/api/validate", {
      method: "POST",
      body,
    });
  } catch {
    throw new ApiError(
      "I can't reach the server. Ask your instructor to start Mod Medic, then try again.",
    );
  }

  if (!response.ok) {
    throw new ApiError(messageForStatus(response.status), response.status);
  }

  return (await response.json()) as ValidateResponse;
}
