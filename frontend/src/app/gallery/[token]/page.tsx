"use client";

import { PropsWithChildren, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import {
  AlbumDetailAPIInterface,
  AlbumDetailInterface,
  MediaInterface,
} from "@/helpers/interfaces";
import { parseAlbumDetail } from "@/helpers/apiParsers";
import { ApiError, apiFetch } from "@/helpers/apiHelper";
import { API_ENDPOINT_URL } from "@/helpers/constants";
import { Button, Input } from "@/components";

type ViewState =
  | { status: "loading" }
  | { status: "password-required"; wrongAttempt: boolean }
  | { status: "not-found" }
  | { status: "ready"; album: AlbumDetailInterface };

const CenteredMessage = ({ children }: PropsWithChildren) => {
  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 text-center text-sm text-neutral-600">
      {children}
    </main>
  );
};

const Lightbox = ({
  items,
  index,
  onClose,
  onIndexChange,
}: {
  items: MediaInterface[];
  index: number;
  onClose: () => void;
  onIndexChange: (i: number) => void;
}) => {
  const item = items[index];

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && index < items.length - 1) onIndexChange(index + 1);
      if (e.key === "ArrowLeft" && index > 0) onIndexChange(index - 1);
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [index, items.length, onClose, onIndexChange]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4">
      <Button
        onClick={onClose}
        className="absolute top-4 right-4 text-2xl text-white/80 hover:text-white"
        aria-label="Cerrar"
      >
        ✕
      </Button>

      {index > 0 && (
        <Button
          onClick={() => onIndexChange(index - 1)}
          className="absolute left-2 text-3xl text-white/70 hover:text-white sm:left-4"
          aria-label="Anterior"
        >
          ‹
        </Button>
      )}
      {index < items.length - 1 && (
        <Button
          onClick={() => onIndexChange(index + 1)}
          className="absolute right-2 text-3xl text-white/70 hover:text-white sm:right-4"
          aria-label="Siguiente"
        >
          ›
        </Button>
      )}

      {item.type === "video" ? (
        <video src={item.fileUrl} controls autoPlay className="max-h-full max-w-full" />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={item.fileUrl}
          alt={item.originalFilename}
          className="max-h-full max-w-full object-contain"
        />
      )}
    </div>
  );
};

const PublicGalleryPage = () => {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [state, setState] = useState<ViewState>({ status: "loading" });
  const [password, setPassword] = useState<string>("");
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const fetchAlbum = useCallback(
    async (pwd?: string) => {
      try {
        const res = await apiFetch(`${API_ENDPOINT_URL.PUBLIC_ALBUM_API}${token}/`, {
          method: pwd !== undefined ? "POST" : "GET",
          body: pwd !== undefined ? JSON.stringify({ password: pwd }) : undefined,
        });

        const data: AlbumDetailAPIInterface = await res.json();
        setState({ status: "ready", album: parseAlbumDetail(data) });
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          setState({ status: "password-required", wrongAttempt: pwd !== undefined });
        } else {
          setState({ status: "not-found" });
        }
      }
    },
    [token],
  );

  useEffect(() => {
    (async () => {
      await fetchAlbum();
    })();
  }, [fetchAlbum]);

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAlbum(password);
  };

  if (state.status === "loading") {
    return <CenteredMessage>Cargando...</CenteredMessage>;
  }

  if (state.status === "not-found") {
    return <CenteredMessage>Este enlace no existe o ya no está disponible.</CenteredMessage>;
  }

  if (state.status === "password-required") {
    return (
      <CenteredMessage>
        <form onSubmit={handlePasswordSubmit} className="w-full max-w-xs text-left">
          <p className="mb-4 text-center text-sm text-neutral-600">Este álbum tiene contraseña.</p>
          <Input
            type="password"
            label="Contraseña"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mb-2 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm text-neutral-900 focus:border-neutral-900 focus:outline-none"
            placeholder="Contraseña"
          />
          {state.wrongAttempt && (
            <p className="mb-2 text-sm text-red-600">Contraseña incorrecta.</p>
          )}
          <Button
            type="submit"
            className="w-full rounded-lg bg-neutral-900 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Entrar
          </Button>
        </form>
      </CenteredMessage>
    );
  }

  const { album } = state;
  const readyMedia = album.media.filter((m) => m.processingStatus === "ready");

  return (
    <main className="min-h-screen bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white px-4 py-8 text-center">
        <h1 className="text-lg font-semibold text-neutral-900">{album.name}</h1>
        {album.description && (
          <p className="mx-auto mt-1 max-w-md text-sm text-neutral-600">{album.description}</p>
        )}
      </header>

      <div className="mx-auto max-w-5xl px-2 py-6">
        {readyMedia.length === 0 ? (
          <p className="text-center text-sm text-neutral-500">
            Todavía no hay fotos en este álbum.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 md:grid-cols-4">
            {readyMedia.map((item, idx) => (
              <button
                key={item.id}
                onClick={() => setLightboxIndex(idx)}
                className="relative aspect-square overflow-hidden rounded-md bg-neutral-100"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={item.thumbnailUrl ?? undefined}
                  alt=""
                  className="h-full w-full object-cover"
                />
                {item.type === "video" && (
                  <span className="absolute inset-0 flex items-center justify-center text-2xl text-white drop-shadow">
                    ▶
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {lightboxIndex !== null && (
        <Lightbox
          items={readyMedia}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onIndexChange={setLightboxIndex}
        />
      )}
    </main>
  );
};

export default PublicGalleryPage;
