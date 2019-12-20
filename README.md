# Nemivir

[![CircleCI](https://circleci.com/gh/TsingJyujing/nemivir.svg?style=svg)](https://circleci.com/gh/TsingJyujing/nemivir)

## Introduction

A unique image database based on seaweedfs.

While you're downloading a lot of image from internet by spider, or managing  a lot duplicated image, you should try it.
This service can help you:

- Manage duplicated images
- Compress image with WEBP format
- Convert image into other format and size while querying

Name from [Nemipterus Virgatus](https://en.wikipedia.org/wiki/Nemipterus_virgatus), a type of very delicious fish.

## Design Note

For now, I'm using seaweed's filer to manage files, by default, filer is using leveldb2 to save meta data.

For now, the bottleneck of the system is the filer, because filer can only be single node.
But there're also a longer plan to use MongoDB to save meta data for more scalable and better data management.
By using MongoDB and redis as distributed locking system, 

### Filer Structure

By default, the port of filer will not be exposed, but you can expose it manually.
In filer, dirs are named by the hash of the image, and all the files in the dir have the same hash.

### Upload logic

**TODO**

## Quick Start

## API Documentation

I'm using FastAPI's doc generator, please running the service and open homepage or http://ip:port/docs for more details.
