from .Bitmap import *
from .Palette import *
from .Tilemap import *
from .Cell import *
from PIL import Image
from ..Common import Tile, Shape, paste_alpha, eightbpp_to_fourbpp, fourbpp_to_eightbpp, empty_im

class NDSImage:
    def __init__(
        self,
        Bitmap : Bitmap = None,
        Palette : Palette = None,
        Tilemap : Tilemap | NSCR = None,
        Cell : NCER = None,
        bit_depth : int = None,
        im_size : tuple[int, int] = None,
        shape_size : tuple[int, int] = (8,8),
        transparency : bool = False,
        linear : bool = False
        ):
        
        self.load_Bitmap(Bitmap)
        self.load_Palette(Palette)
        self.load_Cell(Cell)
        self.load_Tilemap(Tilemap)

        self.set_im_size(im_size)
        self.set_shape_size(shape_size)
        self.set_bit_depth(bit_depth)
        self.set_transparency(transparency)
        self.set_linear(linear)

    def load_Bitmap(self, Bitmap : Bitmap):
        self.Bitmap = Bitmap
        if Bitmap is not None:
            self.set_bit_depth(self.Bitmap.get_bit_depth())
            self.set_im_size(self.Bitmap.get_im_size())
            self.set_linear(self.Bitmap.get_linear_flag())

    def load_Tilemap(self, Tilemap : Tilemap):
        self.Tilemap = Tilemap
        if Tilemap is not None:
            self.set_im_size(self.Tilemap.get_im_size())

    def load_Palette(self, Palette : Palette):
        self.Palette = Palette
        if Palette is not None:
            self.set_bit_depth(self.Palette.get_bit_depth())

    def load_Cell(self, Cell : NCER):
        self.Cell = Cell

    def set_im_size(self, im_size : tuple[int, int]):
        if im_size is not None:
            self.im_size = im_size
            self.im_width, self.im_height = im_size

    def set_shape_size(self, shape_size : tuple[int, int]):
        if shape_size is not None:
            self.shape_size = shape_size
            self.shape_width, self.shape_height = shape_size

    def set_bit_depth(self, bit_depth : int):
        if bit_depth in [4, 8]:

            self.bit_depth = bit_depth

        elif bit_depth is None:
            pass

        else:
            raise Exception('Invalid bit depth value. Should be either 4 or 8.')
        
    def set_linear(self, linear : bool):
        self.linear = linear

    def set_transparency(self, transparency : bool):
        self.transparency = transparency

    def generate_tile_list(self):
        assert self.bit_depth in [4, 8]
        if self.bit_depth == 4:
            tile_datasize = 32
        elif self.bit_depth == 8:
            tile_datasize = 64
        data = self.Bitmap.get_data()
        tile_count = len(data) // tile_datasize
        tiles = [Tile(data[tile_datasize * idx : tile_datasize * (idx + 1)], self.bit_depth, self.linear) for idx in range(tile_count)]
        return tiles

    def build_hor_image(self, pal_idx : int):
        shape_width_count = self.im_width // self.shape_width
        shape_height_count = self.im_height // self.shape_height
        im = empty_im(self.im_size, self.Palette.get_colors(), self.bit_depth, self.transparency)
        tile_idx = 0
        tiles = self.generate_tile_list()
        tile_count_par_shape = (self.shape_width // 8) * (self.shape_height // 8)
        for j in range(shape_height_count):
            for i in range(shape_width_count):
                shape = Shape(tiles[tile_idx : tile_idx + tile_count_par_shape], self.shape_size, pal_idx, self.bit_depth, False)
                tile_idx += tile_count_par_shape
                im.paste(shape.image, (i * self.shape_width, j * self.shape_height))
        return [im]
    
    def build_linear_image(self, pal_idx : int):
        im = empty_im(self.im_size, self.Palette.get_colors(), self.bit_depth, self.transparency)
        if self.bit_depth == 8:
            im.putdata(self.Bitmap.get_data())
        else:
            newdata = fourbpp_to_eightbpp(self.Bitmap.get_data(), pal_idx)
            im.putdata(newdata)
        return [im]
    
    def build_image_with_tilemap(self):
        im = empty_im(self.im_size, self.Palette.get_colors(), self.bit_depth, self.transparency)
        tiles = self.generate_tile_list()
        maps = iter(self.Tilemap.get_map())
        for j in range(im.height // 8):
            for i in range(im.width // 8):
                map_info = next(maps)
                tile = map_info.get_tile(tiles)
                im.paste(tile, (i * 8, j * 8))
        return [im]
    
    def build_cells(self):
        tiles = self.generate_tile_list()
        cell_images = []
        for cell_bank in self.Cell.cebk.cell_banks:
            if len(cell_bank.OAM_data_list) == 0:
                cell_images.append(None)
                continue

            min_x = min([OAM_data.x_pos for OAM_data in cell_bank.OAM_data_list])
            min_y = min([OAM_data.y_pos for OAM_data in cell_bank.OAM_data_list])
            max_x = max([OAM_data.x_pos + OAM_data.shape_size[0] for OAM_data in cell_bank.OAM_data_list])
            max_y = max([OAM_data.y_pos + OAM_data.shape_size[1] for OAM_data in cell_bank.OAM_data_list])
            cell_im_size = (max_x - min_x, max_y - min_y)
            cell_im = empty_im(cell_im_size, self.Palette.get_colors(), self.bit_depth, True)

            if self.bit_depth == 4:
                transparency_idx = [i * 16 for i in range(16)]
            else:
                transparency_idx = [0]
            
            for OAM_data in cell_bank.OAM_data_list[::-1]:
                if self.bit_depth == 4:
                    tile_offset = OAM_data.tile_index * self.Cell.cebk.tile_index_offset
                else:
                    tile_offset = OAM_data.tile_index * self.Cell.cebk.tile_index_offset // 2

                shape = Shape(tiles[tile_offset:], OAM_data.shape_size, OAM_data.pal_idx, self.bit_depth, self.linear)
                shape_im = shape.image
                if OAM_data.ver_flip:
                    shape_im = shape_im.transpose(Image.FLIP_TOP_BOTTOM)
                if OAM_data.hor_flip:
                    shape_im = shape_im.transpose(Image.FLIP_LEFT_RIGHT)

                cell_im = paste_alpha(cell_im, shape_im, (OAM_data.x_pos - min_x, OAM_data.y_pos - min_y), transparency_idx)
            cell_images.append(cell_im)

        return cell_images
        
    def build_im(self, pal_idx : int = 0):
        assert self.Bitmap is not None and self.Palette is not None, "At least a palette and a bitmap are required"
        if self.Cell is not None:
            return self.build_cells()
        elif self.Tilemap is not None:
            return self.build_image_with_tilemap()
        else:
            if not self.linear:
                return self.build_hor_image(pal_idx)
            else:
                return self.build_linear_image(pal_idx)

    def import_image(self, im_filepath : str, cell_idx : int = 0):
        im = Image.open(im_filepath)
        assert im.mode == "P", "Invalid png type, pyNitro is expecting a color indexed png."  
        assert self.Bitmap is not None and self.Palette is not None, "At least a palette and a bitmap are required"
        if self.Cell is not None:
            self.import_cell(im, cell_idx)
        elif self.Tilemap is not None:
            self.import_image_with_tilemap(im)
        else:
            if not self.linear:
                self.import_hor_image(im)
            else:
                self.import_linear_image(im)
            
    def import_cell(self, im : Image.Image, cell_idx : int):
        colors = im.getpalette()
        self.tiles = self.generate_tile_list()
        cell = self.Cell.cebk.cell_banks[cell_idx]
        min_x = min([OAM_data.x_pos for OAM_data in cell.OAM_data_list])
        min_y = min([OAM_data.y_pos for OAM_data in cell.OAM_data_list])

        for OAM_data in cell.OAM_data_list:
            shape = Shape(im.crop((OAM_data.x_pos - min_x, OAM_data.y_pos - min_y, OAM_data.x_pos + OAM_data.shape.width - min_x, OAM_data.y_pos + OAM_data.shape.height - min_y)), OAM_data.shape_size, OAM_data.pal_idx, self.bit_depth, self.linear)
            new_tiles = shape.get_tiles()

            if self.bit_depth == 4:
                tile_offset = OAM_data.tile_index * self.Cell.cebk.tile_index_offset
            else:
                tile_offset = OAM_data.tile_index * self.Cell.cebk.tile_index_offset // 2

            self.tiles[tile_offset : tile_offset + shape.tile_count] = new_tiles

        newdata = bytearray()
        for tile in self.tiles:
            newdata += tile.to_bytes()

        self.Bitmap.set_data(newdata)
        self.Palette.set_colors(colors)

    def import_image_with_tilemap(self, im : Image.Image):
        colors = im.getpalette()
        mapinfos : list[MapInfo] = []
        data = bytes()
        tiles_data : list[bytes] = []
        for j in range(im.height // 8):
            for i in range(im.width // 8):
                tile_data = im.crop((i * 8, j * 8, (i+1) * 8, (j+1) * 8)).tobytes()
                if self.bit_depth == 8:
                    pal_idx = 0
                else:
                    pal_idx = tile_data[0] // 0x10
                if self.bit_depth == 4:
                    tile_data = eightbpp_to_fourbpp(tile_data)
                if tile_data in tiles_data:
                    tile_idx = tiles_data.index(tile_data)
                else:
                    tiles_data.append(tile_data)
                    data += tile_data
                    tile_idx = len(tiles_data) - 1
                map_info = MapInfo()
                map_info.tile_idx = tile_idx
                map_info.pal_idx = pal_idx
                mapinfos.append(map_info)

        self.Bitmap.set_data(data)
        self.Palette.set_colors(colors)
        self.Tilemap.set_map(mapinfos)
        self.Tilemap.set_im_size(im.size)

    def import_hor_image(self, im : Image.Image):
        colors = im.getpalette()
        data = bytearray()
        for j in range(im.height // self.shape_height):
            for i in range(im.width // self.shape_width):
                shape = Shape(im.crop((i * self.shape_width, j * self.shape_height, (i+1) * self.shape_width, (j+1) * self.shape_height)), self.shape_size, 0, self.bit_depth, False)
                data += shape.to_bytes()
        self.Bitmap.set_data(data)
        self.Bitmap.set_im_size(im.size)
        self.Palette.set_colors(colors)
        
    def import_linear_image(self, im : Image.Image):
        colors = im.getpalette()
        data = im.tobytes()
        if self.bit_depth == 4:
            data = eightbpp_to_fourbpp(data)
        self.Bitmap.set_data(data)
        self.Bitmap.set_im_size(im.size)
        self.Palette.set_colors(colors)