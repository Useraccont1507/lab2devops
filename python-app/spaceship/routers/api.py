import numpy as np
from fastapi import APIRouter

router = APIRouter()


@router.get('')
def hello_world() -> dict:
    return {'msg': 'Hello, World! — Illia Verezei'}


@router.get('/matrix')
def matrix_multiply() -> dict:
    a = np.random.randint(0, 100, (10, 10))
    b = np.random.randint(0, 100, (10, 10))
    product = a @ b
    return {
        'matrix_a': a.tolist(),
        'matrix_b': b.tolist(),
        'product': product.tolist(),
    }
