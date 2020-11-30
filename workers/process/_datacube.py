from enum import Enum

import xarray as xr


class DimensionType(str, Enum):
    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    BANDS = "bands"
    OTHER = "other"


class DataCube(xr.DataArray):
    __slots__ = ("dim_types",)

    def __init__(self, *args, dim_types=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.dim_types = {}
        if dim_types is None:
            dim_types = {}
        for dim in self.dims:
            self.dim_types[dim] = dim_types.get(dim, DimensionType.OTHER)

    def __repr__(self):
        repr_str = super().__repr__()
        repr_str = repr_str + "\n" + self.dim_types_repr()
        return repr_str

    def dim_types_repr(self):
        repr_str = "Coordinate types:"
        for dim in self.dim_types.keys():
            dim_type = self.dim_types.get(dim, DimensionType.OTHER)
            repr_str += f"\n  * {dim}: {dim_type}"
        return repr_str

    def _check_if_dim_exists(self, dim):
        if dim not in self.dims:
            raise Exception(f"Dimension '{dim}' not in the datacube")

    def get_dim_type(self, dim):
        self._check_if_dim_exists(dim)
        return self.dim_types.get(dim, DimensionType.OTHER)

    def set_dim_type(self, dim, dimension_type):
        self._check_if_dim_exists(dim)
        self.dim_types[dim] = dimension_type

    def copy(self, new_cube):
        return DimensionTypes(new_cube, types=self.dim_types)

    def get_dims_of_type(self, dimension_type):
        dims_of_type = []
        for dim in self.dims:
            if self.dim_types[dim] == dimension_type:
                dims_of_type.append(dim)
        return tuple(dims_of_type)

    def get_dim_types(self):
        return self.dim_types

    @staticmethod
    def from_dataarray(dataarray, dim_types=None):
        return DataCube(
            dataarray.data, dims=dataarray.dims, coords=dataarray.coords, attrs=dataarray.attrs, dim_types=dim_types
        )

    def copy(self, *args, **kwargs):
        c = super().copy(*args, **kwargs)
        c.dim_types = {**self.dim_types}
        return c

    def expand_dims(self, dim=None, dim_types={}, **kwargs):
        c = super().expand_dims(dim=dim, **kwargs)
        c.dim_types = {**self.dim_types}
        if isinstance(dim, dict):
            for dimension in dim.keys():
                c.set_dim_type(dimension, dim_types.get(dimension, DimensionType.OTHER))
        elif isinstance(dim, list):
            for dimension in dim:
                c.set_dim_type(dimension, dim_types.get(dimension, DimensionType.OTHER))
        else:
            c.set_dim_type(dim, dim_types.get(dim, DimensionType.OTHER))
        return c

    @staticmethod
    def full_like(other, *args, **kwargs):
        x = DataCube.from_dataarray(xr.full_like(other, *args, **kwargs))
        x.dim_types = {**other.dim_types}
        return x

    def squeeze(self, *args, **kwargs):
        x = super().squeeze(*args, **kwargs)
        return DataCube.from_dataarray(x, dim_types={**self.dim_types})

    def _add_filtered_dim_types(self, x, dim):
        original_dim_types = {**self.dim_types}

        if dim is not None:
            if isinstance(dim, list):
                for dimension in dim:
                    del original_dim_types[dimension]
            else:
                del original_dim_types[dim]
        x.dim_types = original_dim_types
        return x

    def sum(self, dim=None, *args, **kwargs):
        x = super().sum(dim=dim, *args, **kwargs)
        return self._add_filtered_dim_types(x, dim)

    def max(self, dim=None, *args, **kwargs):
        x = super().max(dim=dim, *args, **kwargs)
        return self._add_filtered_dim_types(x, dim)

    def min(self, dim=None, *args, **kwargs):
        x = super().min(dim=dim, *args, **kwargs)
        return self._add_filtered_dim_types(x, dim)

    def mean(self, dim=None, *args, **kwargs):
        x = super().mean(dim=dim, *args, **kwargs)
        return self._add_filtered_dim_types(x, dim)

    def median(self, dim=None, *args, **kwargs):
        x = super().median(dim=dim, *args, **kwargs)
        return self._add_filtered_dim_types(x, dim)

    def prod(self, dim=None, *args, **kwargs):
        x = super().prod(dim=dim, *args, **kwargs)
        return self._add_filtered_dim_types(x, dim)

    @staticmethod
    def concat(objs, *args, **kwargs):
        original_dim_types = {}
        for obj in objs:
            original_dim_types.update(obj.dim_types)
        x = xr.concat(objs, *args, **kwargs)
        return DataCube.from_dataarray(x, dim_types=original_dim_types)

    def _add_appropriate_dim_types(self, other, x):
        if isinstance(other, DataCube):
            x.dim_types = {**other.dim_types, **self.dim_types}
        else:
            x.dim_types = {**self.dim_types}
        return x

    def __add__(self, other):
        x = super().__add__(other)
        return self._add_appropriate_dim_types(other, x)

    def __sub__(self, other):
        x = super().__sub__(other)
        return self._add_appropriate_dim_types(other, x)

    def __truediv__(self, other):
        x = super().__truediv__(other)
        return self._add_appropriate_dim_types(other, x)

    def __mul__(self, other):
        x = super().__mul__(other)
        return self._add_appropriate_dim_types(other, x)

    def _get_and_set_existing_dim_types(self, x):
        original_dim_types = {**self.dim_types}
        for dim in self.dims:
            if dim not in x.dims:
                del original_dim_types[dim]
        x.dim_types = original_dim_types
        return x

    def sel(self, *args, **kwargs):
        x = super().sel(*args, **kwargs)
        return self._get_and_set_existing_dim_types(x)

    def isel(self, *args, **kwargs):
        x = super().isel(*args, **kwargs)
        return self._get_and_set_existing_dim_types(x)

    def where(self, *args, **kwargs):
        x = DataCube.from_dataarray(super().where(*args, **kwargs))
        return self._get_and_set_existing_dim_types(x)

    @staticmethod
    def get_where(*args, **kwargs):
        x = xr.where(*args, **kwargs)
        return DataCube.from_dataarray(x)
