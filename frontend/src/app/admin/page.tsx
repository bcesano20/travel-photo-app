"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { API_ENDPOINT_URL, ERROR_MESSAGES, ROUTES } from "@/helpers/constants";
import { AlbumListItemAPIInterface, AlbumListItemInterface } from "@/helpers/interfaces";
import { parseAlbumListItem } from "@/helpers/apiParsers";
import { ApiError, apiDelete, apiGet } from "@/helpers/apiHelper";
import { Button, EditAlbumModal, NewAlbumModal } from "@/components";

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

const AdminDashboard = () => {
  const [albums, setAlbums] = useState<AlbumListItemInterface[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState<boolean>(false);
  const [editingAlbumId, setEditingAlbumId] = useState<number | null>(null);

  const loadAlbums = async () => {
    try {
      const data = await apiGet<AlbumListItemAPIInterface[]>(API_ENDPOINT_URL.ALBUMS_API);

      setAlbums(data.map(parseAlbumListItem));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ERROR_MESSAGES.ALBUMS_NOT_LOAD);
    }
  };

  useEffect(() => {
    (async () => {
      await loadAlbums();
    })();
  }, []);

  const handleDelete = async (album: AlbumListItemInterface) => {
    if (!window.confirm(`¿Eliminar el álbum "${album.name}"?`)) return;

    try {
      await apiDelete(`${API_ENDPOINT_URL.ALBUMS_API}${album.id}/`);
      loadAlbums();
    } catch {
      setError(ERROR_MESSAGES.ALBUM_NOT_DELETED);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-[25px] font-semibold text-white md:text-[30px]">Tus álbumes</h1>
        <Button variant="primary" onClick={() => setShowForm(true)}>
          + Nuevo álbum
        </Button>
      </div>

      <NewAlbumModal
        open={showForm}
        onClose={() => setShowForm(false)}
        onCreated={() => {
          setShowForm(false);
          loadAlbums();
        }}
      />

      <EditAlbumModal
        albumId={editingAlbumId}
        onClose={() => setEditingAlbumId(null)}
        onUpdated={() => {
          setEditingAlbumId(null);
          loadAlbums();
        }}
      />

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {albums === null && !error && <p className="text-sm text-neutral-500">Cargando...</p>}

      {albums !== null && albums.length === 0 && (
        <p className="text-sm text-neutral-500">Todavía no creaste ningún álbum.</p>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
        {albums?.map((album) => (
          <Link
            key={album.id}
            href={`${ROUTES.ALBUM}/${album.id}`}
            className="group overflow-hidden rounded-xl border border-neutral-200 bg-white transition hover:shadow-md"
          >
            <div className="aspect-square bg-neutral-100">
              {album.coverThumbnailUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={album.coverThumbnailUrl}
                  alt={album.name}
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
                <p className="truncate text-sm font-medium text-neutral-900">{album.name}</p>
                <p className="text-xs text-neutral-500">
                  {album.mediaCount} {album.mediaCount === 1 ? "archivo" : "archivos"}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setEditingAlbumId(album.id);
                  }}
                  aria-label="Editar álbum"
                  className="cursor-pointer rounded p-1 text-neutral-400 hover:text-neutral-700"
                >
                  <PencilIcon />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleDelete(album);
                  }}
                  aria-label="Eliminar álbum"
                  className="cursor-pointer rounded p-1 text-neutral-400 hover:text-red-600"
                >
                  <TrashIcon />
                </button>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default AdminDashboard;
