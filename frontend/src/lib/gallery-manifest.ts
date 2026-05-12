/**
 * Drop portrait files into frontend/public/gallery/ as 01.jpg … 10.jpg (or .png — update imageSrc).
 * Then set character + book labels below for captions under each tile.
 */
export type GalleryItem = {
  id: string;
  /** URL path under public/, e.g. /gallery/01.jpg */
  imageSrc: string;
  character: string;
  book: string;
};

export const GALLERY_ITEMS: GalleryItem[] = [
  { id: '1', imageSrc: '/gallery/01.jpg', character: '', book: '' },
  { id: '2', imageSrc: '/gallery/02.jpg', character: '', book: '' },
  { id: '3', imageSrc: '/gallery/03.jpg', character: '', book: '' },
  { id: '4', imageSrc: '/gallery/04.jpg', character: '', book: '' },
  { id: '5', imageSrc: '/gallery/05.jpg', character: '', book: '' },
  { id: '6', imageSrc: '/gallery/06.jpg', character: '', book: '' },
  { id: '7', imageSrc: '/gallery/07.jpg', character: '', book: '' },
  { id: '8', imageSrc: '/gallery/08.jpg', character: '', book: '' },
  { id: '9', imageSrc: '/gallery/09.jpg', character: '', book: '' },
  { id: '10', imageSrc: '/gallery/10.jpg', character: '', book: '' },
];
