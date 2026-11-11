/**
 * Portraits in frontend/public/gallery/ as 01.jpg … (see GALLERY_ITEMS).
 * Captions below match each file order.
 */
export type GalleryItem = {
  id: string;
  /** URL path under public/, e.g. /gallery/01.jpg */
  imageSrc: string;
  character: string;
  book: string;
  /** Words from the book this portrait was built on (shown on the home page). */
  quote?: string;
};

export const GALLERY_ITEMS: GalleryItem[] = [
  { id: '1', imageSrc: '/gallery/01.jpg', character: 'Elizabeth Bennet', book: 'Pride and Prejudice', quote: 'rendered uncommonly intelligent by the beautiful expression of her dark eyes' },
  { id: '2', imageSrc: '/gallery/02.jpg', character: 'Mr. Darcy', book: 'Pride and Prejudice', quote: 'his fine, tall person, handsome features, noble mien' },
  { id: '3', imageSrc: '/gallery/03.jpg', character: 'Edward Rochester', book: 'Jane Eyre' },
  { id: '4', imageSrc: '/gallery/04.jpg', character: 'Jane Eyre', book: 'Jane Eyre', quote: 'I had green eyes, reader' },
  { id: '5', imageSrc: '/gallery/05.jpg', character: 'Count Dracula', book: 'Dracula', quote: 'a tall, thin man, clad in black' },
  { id: '6', imageSrc: '/gallery/06.jpg', character: 'Dorian Gray', book: 'The Picture of Dorian Gray', quote: 'his finely curved scarlet lips, his frank blue eyes, his crisp gold hair' },
  { id: '7', imageSrc: '/gallery/07.jpg', character: 'Jo March', book: 'Little Women' },
];
