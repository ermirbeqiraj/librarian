# The Librarian image: both hosts built in the SDK stage, published into the aspnet runtime.
# The Api is the entrypoint; the Ingest runs from the same image with the entrypoint overridden
# (compose at the deploy: ["dotnet", "ingest/Librarian.Ingest.dll"]).
# The image carries appsettings.json only: every machine path, port and secret comes from the
# environment, and appsettings.{Environment}.json never enters Git.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY Directory.Build.props Directory.Packages.props nuget.config ./
COPY src/Librarian.Application/Librarian.Application.csproj src/Librarian.Application/packages.lock.json src/Librarian.Application/
COPY src/Librarian.Adapters/Librarian.Adapters.csproj src/Librarian.Adapters/packages.lock.json src/Librarian.Adapters/
COPY src/Librarian.Api/Librarian.Api.csproj src/Librarian.Api/packages.lock.json src/Librarian.Api/
COPY src/Librarian.Ingest/Librarian.Ingest.csproj src/Librarian.Ingest/packages.lock.json src/Librarian.Ingest/
RUN dotnet restore src/Librarian.Api/Librarian.Api.csproj --locked-mode \
    && dotnet restore src/Librarian.Ingest/Librarian.Ingest.csproj --locked-mode

COPY . .
RUN dotnet publish src/Librarian.Api -c Release -o /publish/api --no-restore \
    && dotnet publish src/Librarian.Ingest -c Release -o /publish/ingest --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /publish/api api
COPY --from=build /publish/ingest ingest
ENV DOTNET_ENVIRONMENT=Production
ENTRYPOINT ["dotnet", "api/Librarian.Api.dll"]
