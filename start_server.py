#!/usr/bin/python3

import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        "nemivir.service.image_api:app",
        reload=True,
    )
