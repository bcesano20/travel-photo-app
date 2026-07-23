"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import {
  AlbumDetailAPIInterface,
  AlbumDetailInterface,
  MediaAPIInterface,
  ShareLinkAPIInterface,
  ShareLinkInterface,
} from "@/helpers/interfaces";
import { parseAlbumDetail, parseMedia, parseShareLink } from "@/helpers/apiParsers";
import { ApiError, apiGet, apiPatch, apiPost } from "@/helpers/apiHelper";
import { API_ENDPOINT_URL, ERROR_MESSAGES } from "@/helpers/constants";
import { Button, Input } from "@/components";

interface UploadItem {
  id: string;
  fileName: string;
  status: "uploading" | "confirming" | "done" | "error";
  error?: string;
}

const ShareLinkPanel = ({ albumId }: { albumId: number }) => {
  const [link, setLink] = useState<ShareLinkInterface | null | undefined>(undefined);
  const [copied, setCopied] = useState<boolean>(false);

  const loadLink = useCallback(async () => {
    const links = await apiGet<ShareLinkAPIInterface[]>(
      `${API_ENDPOINT_URL.SHARE_LINKS_API}?album=${albumId}`,
    );
    setLink(links.map(parseShareLink).find((l) => l.isActive) ?? null);
  }, [albumId]);

  useEffect(() => {
    (async () => {
      await loadLink();
    })();
  }, [loadLink]);

  const handleCreate = async () => {
    await apiPost(API_ENDPOINT_URL.SHARE_LINKS_API, { album: albumId });
    loadLink();
  };

  const handleRevoke = async () => {
    if (!link) return;
    await apiPatch(`${API_ENDPOINT_URL.SHARE_LINKS_API}/${link.id}/`, { is_active: false });
    loadLink();
  };

  const fullUrl = (token: string) => {
    return `${window.location.origin}/gallery/${token}`;
  };

  const handleCopy = async () => {
    if (!link) return;
    await navigator.clipboard.writeText(fullUrl(link.token));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (link === undefined) return null;

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-neutral-900">Enlace para compartir</h2>
      {link ? (
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded bg-neutral-100 px-2 py-1 text-xs text-neutral-700">
            {fullUrl(link.token)}
          </code>
          <Button variant="secondary" onClick={handleCopy} className="text-xs">
            {copied ? "¡Copiado!" : "Copiar"}
          </Button>
          <Button variant="danger" onClick={handleRevoke} className="text-xs">
            Revocar
          </Button>
        </div>
      ) : (
        <Button variant="secondary" onClick={handleCreate}>
          Crear enlace
        </Button>
      )}
    </div>
  );
};

const AlbumDetailPage = () => {
  const params = useParams<{ id: string }>();
  const albumId = params.id;

  const [album, setAlbum] = useState<AlbumDetailInterface | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadAlbum = useCallback(async () => {
    try {
      const data = await apiGet<AlbumDetailAPIInterface>(
        `${API_ENDPOINT_URL.ALBUMS_API}${albumId}/`,
      );
      setAlbum(parseAlbumDetail(data));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ERROR_MESSAGES.ALBUMS_NOT_LOAD);
    }
  }, [albumId]);

  useEffect(() => {
    (async () => {
      await loadAlbum();
    })();
  }, [loadAlbum]);

  // While any media is still "pending", poll every few seconds so
  // thumbnails pop in once the worker finishes, without a manual refresh.
  useEffect(() => {
    const hasPending = album?.media.some((m) => m.processingStatus === "pending");
    if (!hasPending) return;
    const interval = setInterval(loadAlbum, 3000);
    return () => clearInterval(interval);
  }, [album, loadAlbum]);

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    for (const file of Array.from(files)) {
      const uploadId = `${file.name}-${Date.now()}`;
      setUploads((prev) => [...prev, { id: uploadId, fileName: file.name, status: "uploading" }]);

      try {
        const mediaType = file.type.startsWith("video/") ? "video" : "photo";

        const { media, upload_url: uploadUrl } = await apiPost<{
          media: MediaAPIInterface;
          upload_url: string;
        }>(API_ENDPOINT_URL.PRESIGNED_UPLOAD_API, {
          album: Number(albumId),
          original_filename: file.name,
          content_type: file.type || "application/octet-stream",
          size: file.size,
          type: mediaType,
        });
        const parsedMedia = parseMedia(media);

        const putRes = await fetch(uploadUrl, {
          method: "PUT",
          headers: { "Content-Type": file.type || "application/octet-stream" },
          body: file,
        });
        if (!putRes.ok) {
          throw new Error("Falló la subida a R2.");
        }

        setUploads((prev) =>
          prev.map((u) => (u.id === uploadId ? { ...u, status: "confirming" } : u)),
        );

        await apiPost(`/${API_ENDPOINT_URL.MEDIA_API}${parsedMedia.id}/confirm/`);

        setUploads((prev) => prev.map((u) => (u.id === uploadId ? { ...u, status: "done" } : u)));
        loadAlbum();
      } catch (err) {
        setUploads((prev) =>
          prev.map((u) =>
            u.id === uploadId
              ? { ...u, status: "error", error: err instanceof Error ? err.message : "Error" }
              : u,
          ),
        );
      }
    }
  };

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!album) return <p className="text-sm text-neutral-500">Cargando...</p>;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-neutral-900">{album.name}</h1>
        {album.description && <p className="mt-1 text-sm text-neutral-600">{album.description}</p>}
      </div>

      <ShareLinkPanel albumId={album.id} />

      <div className="mt-8 mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-neutral-900">Fotos y videos</h2>
        <div>
          <div className="hidden">
            <Input
              ref={fileInputRef}
              label="Subir archivos"
              type="file"
              multiple
              accept="image/*,video/*"
              onChange={(e) => handleFilesSelected(e.target.files)}
            />
          </div>
          <Button onClick={() => fileInputRef.current?.click()}>+ Subir archivos</Button>
        </div>
      </div>

      {uploads.length > 0 && (
        <ul className="mb-6 space-y-1 text-xs text-neutral-500">
          {uploads.map((u) => (
            <li key={u.id}>
              {u.fileName} — {u.status === "error" ? `error: ${u.error}` : u.status}
            </li>
          ))}
        </ul>
      )}

      {album.media.length === 0 ? (
        <p className="text-sm text-neutral-500">Todavía no hay fotos ni videos en este álbum.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {album.media.map((item) => (
            <div key={item.id} className="aspect-square overflow-hidden rounded-lg bg-neutral-100">
              {item.processingStatus === "ready" && item.thumbnailUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={item.thumbnailUrl}
                  alt={item.originalFilename}
                  className="h-full w-full object-cover"
                />
              ) : item.processingStatus === "error" ? (
                <div className="flex h-full w-full items-center justify-center text-xs text-red-500">
                  Error
                </div>
              ) : (
                <div className="flex h-full w-full items-center justify-center text-xs text-neutral-400">
                  Procesando...
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AlbumDetailPage;
