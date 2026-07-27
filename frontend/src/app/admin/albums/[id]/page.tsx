"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import {
  AlbumDetailAPIInterface,
  AlbumDetailInterface,
  MediaAPIInterface,
  MediaInterface,
  ShareLinkAPIInterface,
  ShareLinkInterface,
} from "@/helpers/interfaces";
import { parseAlbumDetail, parseMedia, parseShareLink } from "@/helpers/apiParsers";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "@/helpers/apiHelper";
import { API_ENDPOINT_URL, ERROR_MESSAGES, ROUTES } from "@/helpers/constants";
import { Button, EditAlbumModal, Input, NewAlbumModal } from "@/components";

interface UploadItem {
  id: string;
  fileName: string;
  status: "uploading" | "confirming" | "done" | "error";
  error?: string;
}

const XIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    className="h-3.5 w-3.5"
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6 6 18" />
  </svg>
);

const PencilIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M16.862 4.487a2.06 2.06 0 0 1 2.915 2.914L8.5 18.678l-4 1 1-4Z"
    />
  </svg>
);

const TrashIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M4 7h16M9 7V4h6v3m-7 0 .8 12.8A2 2 0 0 0 10.79 20h2.42a2 2 0 0 0 2-1.99L16 7"
    />
  </svg>
);

const SubAlbumsSection = ({
  album,
  onChanged,
}: {
  album: AlbumDetailInterface;
  onChanged: () => void;
}) => {
  const [showNewSubAlbum, setShowNewSubAlbum] = useState<boolean>(false);
  const [editingChildId, setEditingChildId] = useState<number | null>(null);
  const [childError, setChildError] = useState<string | null>(null);

  const handleDeleteChild = async (child: AlbumDetailInterface) => {
    if (!window.confirm(`¿Eliminar el sub-álbum "${child.name}"?`)) return;

    setChildError(null);
    try {
      await apiDelete(`${API_ENDPOINT_URL.ALBUMS_API}${child.id}/`);
      onChanged();
    } catch {
      setChildError(ERROR_MESSAGES.ALBUM_NOT_DELETED);
    }
  };

  return (
    <div className="mt-8">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[25px] font-semibold text-white md:text-[30px]">Sub-álbumes</h2>
        <Button onClick={() => setShowNewSubAlbum(true)}>+ Nuevo sub-álbum</Button>
      </div>

      <NewAlbumModal
        open={showNewSubAlbum}
        parentId={album.id}
        onClose={() => setShowNewSubAlbum(false)}
        onCreated={() => {
          setShowNewSubAlbum(false);
          onChanged();
        }}
      />

      <EditAlbumModal
        albumId={editingChildId}
        onClose={() => setEditingChildId(null)}
        onUpdated={() => {
          setEditingChildId(null);
          onChanged();
        }}
      />

      {childError && <p className="mb-4 text-sm text-red-600">{childError}</p>}

      {album.children.length === 0 ? (
        <p className="text-sm text-white">Todavía no creaste ningún sub-álbum.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
          {album.children.map((child) => (
            <Link
              key={child.id}
              href={`${ROUTES.ALBUM}/${child.id}`}
              className="group overflow-hidden rounded-xl border border-neutral-200 bg-white transition hover:shadow-md"
            >
              <div className="aspect-square bg-neutral-100">
                {child.coverThumbnailUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={child.coverThumbnailUrl}
                    alt={child.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-neutral-400">
                    Sin fotos
                  </div>
                )}
              </div>
              <div className="flex items-start justify-between gap-2 p-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-neutral-900">{child.name}</p>
                  <p className="text-xs text-neutral-500">
                    {child.media.length} {child.media.length === 1 ? "archivo" : "archivos"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setEditingChildId(child.id);
                    }}
                    aria-label="Editar sub-álbum"
                    className="cursor-pointer rounded p-1 text-neutral-400 hover:text-neutral-700"
                  >
                    <PencilIcon />
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleDeleteChild(child);
                    }}
                    aria-label="Eliminar sub-álbum"
                    className="cursor-pointer rounded p-1 text-neutral-400 hover:text-red-600"
                  >
                    <TrashIcon />
                  </button>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

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
  const [mediaError, setMediaError] = useState<string | null>(null);
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

  const handleRemoveMedia = async (item: MediaInterface) => {
    if (!window.confirm("¿Quitar este archivo del álbum?")) return;

    setMediaError(null);
    try {
      await apiDelete(`${API_ENDPOINT_URL.MEDIA_API}${item.id}/`);
      loadAlbum();
    } catch {
      setMediaError(ERROR_MESSAGES.MEDIA_NOT_DELETED);
    }
  };

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!album) return <p className="text-[32px] text-white">Cargando...</p>;

  return (
    <div>
      <Link
        href={ROUTES.ADMIN}
        className="mb-4 inline-block text-sm text-neutral-300 hover:text-white"
      >
        <Button>← Volver</Button>
      </Link>

      <div className="mb-6">
        <h1 className="text-[25px] font-bold text-white md:text-[32px]">{album.name}</h1>
        {album.description && <p className="mt-1 text-sm text-white">{album.description}</p>}
      </div>

      {!album.parent && <ShareLinkPanel albumId={album.id} />}

      <div className="mt-8 mb-4 flex items-center justify-between">
        <h2 className="text-[25px] font-semibold text-white md:text-[30px]">Fotos y videos</h2>
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

      {mediaError && <p className="mb-4 text-sm text-red-600">{mediaError}</p>}

      {album.media.length === 0 ? (
        <p className="text-sm text-white">Todavía no hay fotos ni videos en este álbum.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {album.media.map((item) => (
            <div
              key={item.id}
              className="group relative aspect-square overflow-hidden rounded-lg bg-neutral-100"
            >
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

              <button
                type="button"
                onClick={() => handleRemoveMedia(item)}
                aria-label="Quitar del álbum"
                className="absolute top-1.5 right-1.5 flex h-6 w-6 cursor-pointer items-center justify-center rounded-full bg-black/60 text-white opacity-0 transition-opacity group-hover:opacity-100 hover:bg-black/80"
              >
                <XIcon />
              </button>
            </div>
          ))}
        </div>
      )}

      {!album.parent && <SubAlbumsSection album={album} onChanged={loadAlbum} />}
    </div>
  );
};

export default AlbumDetailPage;
