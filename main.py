import uvicorn
import os

if __name__ == "__main__":
    uvicorn.run(
        "src.index:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )

# import uvicorn
#
# if __name__ == "__main__":
#     uvicorn.run("src.index:app", host="localhost", port=8000, reload=True)
